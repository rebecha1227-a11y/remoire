/**
 * Small courier between Photon and Remoire.
 * It does not store persona, memories, or model keys of its own.
 * Credentials are fetched from the local Remoire API on each connection.
 */

const API_BASE = (process.env.REMOIRE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const TOKEN = process.env.IMESSAGE_BRIDGE_TOKEN || "";
const RETRY_DELAYS = [5_000, 15_000, 30_000, 60_000, 120_000, 300_000];

const spaces = new Map();
const inboundMessages = new Map();

function headers() {
  return {
    "Content-Type": "application/json",
    "X-Remoire-Bridge": TOKEN,
  };
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.ok === false) {
    const error = new Error(`remoire_http_${response.status}`);
    error.status = response.status;
    throw error;
  }
  return body.data;
}

async function reportStatus(status, detail = "", extra = {}) {
  try {
    await api("/api/internal/imessage/status", {
      method: "POST",
      body: JSON.stringify({ status, detail, ...extra }),
    });
  } catch {
    /* status reporting must not stop the courier */
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkLineOwnership(projectId, projectSecret, linePhone) {
  if (!projectId || !projectSecret || !linePhone) return "skip";
  const auth = Buffer.from(`${projectId}:${projectSecret}`).toString("base64");
  let response;
  try {
    response = await fetch(`https://spectrum.photon.codes/projects/${projectId}/users/`, {
      headers: { Authorization: `Basic ${auth}` },
    });
  } catch {
    return "unknown";
  }
  if (response.status === 401 || response.status === 403) return "denied";
  if (!response.ok) return "unknown";
  const body = await response.json().catch(() => null);
  const users = body?.data?.users || body?.data || [];
  if (!Array.isArray(users)) return "unknown";
  const owned = users.some((user) => user?.assignedPhoneNumber === linePhone);
  return owned ? "ok" : "changed";
}

async function executeAction(action) {
  const space = spaces.get(action.chat_guid) || [...spaces.values()].at(-1);
  if (action.kind === "read") {
    const message = inboundMessages.get(action.ref_id);
    if (!space || !message) return true;
    try {
      const { read } = await import("spectrum-ts");
      await space.send(read(message));
    } catch {
      return true;
    }
    return true;
  }
  if (action.kind === "typing_start") {
    if (!space?.startTyping) return true;
    try {
      await space.startTyping();
    } catch {
      /* typing is decoration; a failure must not block the reply */
    }
    return true;
  }
  if (action.kind === "typing_stop") {
    if (!space?.stopTyping) return true;
    try {
      await space.stopTyping();
    } catch {
      /* ignore */
    }
    return true;
  }
  if (action.kind === "send") {
    if (!space?.send) return false;
    if (action.delay_ms > 0) await sleep(action.delay_ms);
    await space.send(action.body);
    return true;
  }
  return true;
}

async function pumpOutbox(stop) {
  while (!stop.stopped) {
    let actions = [];
    try {
      const data = await api("/api/internal/imessage/outbox");
      actions = data?.actions || [];
    } catch {
      await sleep(1000);
      continue;
    }
    const next = actions[0];
    if (!next) {
      await sleep(400);
      continue;
    }
    let ok = false;
    try {
      ok = await executeAction(next);
    } catch {
      ok = false;
    }
    try {
      await api(`/api/internal/imessage/outbox/${next.id}`, {
        method: "POST",
        body: JSON.stringify({ ok }),
      });
    } catch {
      await sleep(1000);
    }
    if (!ok) await reportStatus("failed", "有一条消息没能发到 iMessage");
  }
}

async function connectOnce(runtime, stop) {
  const { Spectrum } = await import("spectrum-ts");
  const { imessage } = await import("@spectrum-ts/imessage");
  await reportStatus("connecting", "");
  const ownership = await checkLineOwnership(runtime.project_id, runtime.project_secret, runtime.line_phone);
  if (ownership === "changed") {
    await reportStatus("line_changed", "线路号码已变化，请重新开通");
    return;
  }
  if (ownership === "denied") {
    await reportStatus("failed", "Photon 凭据被拒绝");
    return;
  }
  const instance = await Spectrum({
    projectId: runtime.project_id,
    projectSecret: runtime.project_secret,
    providers: [imessage.config()],
  });
  await reportStatus("connected", "");
  try {
    for await (const [space, message] of instance.messages) {
      if (stop.stopped) break;
      if (message.direction === "outbound") continue;
      if (message.platform && message.platform !== "imessage") continue;
      const externalId = String(message.id || "");
      if (!externalId) continue;
      const chatGuid = message.space?.id || message.sender?.id || "";
      if (chatGuid) spaces.set(chatGuid, space);
      inboundMessages.set(externalId, message);
      if (inboundMessages.size > 200) {
        const oldest = inboundMessages.keys().next().value;
        inboundMessages.delete(oldest);
      }
      const text = flattenText(message.content);
      await api("/api/internal/imessage/inbound", {
        method: "POST",
        body: JSON.stringify({
          external_id: externalId,
          sender: message.sender?.id || "",
          text,
          sent_at: message.dateCreated || "",
          chat_guid: chatGuid,
        }),
      });
    }
  } finally {
    try {
      await instance.stop();
    } catch {
      /* ignore */
    }
  }
}

function flattenText(content) {
  if (!content) return "";
  if (typeof content === "string") return content;
  if (content.type === "text") return content.text || content.body || "";
  if (Array.isArray(content.parts)) {
    return content.parts.map((part) => flattenText(part)).filter(Boolean).join("\n");
  }
  return content.text || content.body || "";
}

async function main() {
  if (!TOKEN) {
    console.error("缺少 IMESSAGE_BRIDGE_TOKEN");
    process.exit(1);
  }
  const stop = { stopped: false };
  const pump = pumpOutbox(stop);
  let attempt = 0;
  while (!stop.stopped) {
    let runtime;
    try {
      runtime = await api("/api/internal/imessage/runtime");
    } catch {
      await sleep(RETRY_DELAYS[Math.min(attempt, RETRY_DELAYS.length - 1)]);
      attempt += 1;
      continue;
    }
    if (!runtime?.enabled || !runtime.project_id || !runtime.project_secret) {
      await reportStatus("unconfigured", "");
      await sleep(5000);
      continue;
    }
    try {
      await connectOnce(runtime, stop);
      attempt = 0;
    } catch {
      await reportStatus("failed", "iMessage 连接中断，正在重试");
      await sleep(RETRY_DELAYS[Math.min(attempt, RETRY_DELAYS.length - 1)]);
      attempt += 1;
    }
  }
  await pump;
}

main();
