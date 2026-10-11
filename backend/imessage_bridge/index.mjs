import { normalizeInboundWithImages, sendAction } from "./protocol.mjs";

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
let provider = null;
let linePhone = "";

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
  let space = spaces.get(action.chat_guid);
  if (!space && provider && action.chat_guid) {
    space = await provider.space.get(action.chat_guid, { phone: linePhone });
    if (space) spaces.set(action.chat_guid, space);
  }
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
  if (["send", "reply", "reaction", "image"].includes(action.kind)) {
    if (!space?.send) return false;
    if (action.delay_ms > 0) await sleep(action.delay_ms);
    const builders = await import("spectrum-ts");
    let media = null;
    if (action.kind === "image") {
      const response = await fetch(`${API_BASE}/api/internal/imessage/outbox/${encodeURIComponent(action.id)}/image`, { headers: headers(), signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error("imessage_image_download_failed");
      const length = Number(response.headers.get("content-length"));
      if (!length || length > 8 * 1024 * 1024) throw new Error("imessage_image_size_invalid");
      const data = Buffer.from(await response.arrayBuffer());
      if (data.length !== length) throw new Error("imessage_image_size_invalid");
      media = { data, mimeType: response.headers.get("content-type")?.split(";")[0] };
    }
    const sent = await sendAction(space, action, builders, media);
    if (!sent?.id) throw new Error("imessage_send_missing_id");
    return { external_id: String(sent.id) };
  }
  return false;
}

async function pumpOutbox(stop) {
  let unacked = null;
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
    let result = unacked?.id === next.id ? unacked.result : null;
    if (result === null) {
      try { result = await executeAction(next); } catch { result = false; }
      unacked = { id: next.id, result };
    }
    const ok = Boolean(result);
    try {
      await api(`/api/internal/imessage/outbox/${next.id}`, {
        method: "POST",
        body: JSON.stringify({ ok, external_id: result?.external_id || "" }),
      });
      unacked = null;
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
  provider = imessage(instance);
  linePhone = runtime.line_phone;
  await reportStatus("connected", "");
  try {
    for await (const [space, message] of instance.messages) {
      if (stop.stopped) break;
      const payload = await normalizeInboundWithImages(message, space.id, runtime.owner_phone);
      if (!payload) continue;
      spaces.set(payload.chat_guid, space);
      inboundMessages.set(payload.external_id, message);
      if (inboundMessages.size > 200) inboundMessages.delete(inboundMessages.keys().next().value);
      await api("/api/internal/imessage/inbound", {
        method: "POST", body: JSON.stringify(payload),
      });
    }
  } finally {
    provider = null;
    spaces.clear();
    inboundMessages.clear();
    try {
      await instance.stop();
    } catch {
      /* ignore */
    }
  }
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
