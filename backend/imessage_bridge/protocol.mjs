/** Pure normalization and send helpers; importing this file never opens a line. */
export function textContent(content, depth = 0) {
  if (!content || depth > 8) return "";
  if (typeof content === "string") return content;
  if (content.type === "text") return content.text || "";
  if (content.type === "reply") return textContent(content.content, depth + 1);
  if (content.type === "group" && Array.isArray(content.items)) {
    return content.items.map(item => textContent(item.content, depth + 1)).filter(Boolean).join("\n");
  }
  return "";
}

export function normalizeInbound(message, fallbackSpace = "", allowAttachment = false) {
  if (message.direction === "outbound" || (message.platform && message.platform !== "imessage")) return null;
  const external_id = String(message.id || "");
  if (!external_id) return null;
  const content = message.content;
  const base = {
    external_id, sender: message.sender?.id || "", chat_guid: message.space?.id || fallbackSpace,
    sent_at: message.timestamp || message.dateCreated || "",
  };
  if (content?.type === "reaction") {
    if (!content.target?.id || !content.emoji) return null;
    return { ...base, kind: "reaction", target_id: String(content.target.id), emoji: content.emoji, target_text: textContent(content.target.content).slice(0, 2000) };
  }
  const text = textContent(content);
  if (!text.trim() && !(allowAttachment && imageAttachments(content).length)) return null;
  return { ...base, kind: "text", text,
    reply_to: content?.type === "reply" ? String(content.target?.id || "") : "",
    quote_text: content?.type === "reply" ? textContent(content.target?.content).slice(0, 2000) : "",
  };
}

export async function sendAction(space, action, builders, media = null) {
  if (!space || space.id !== action.chat_guid) throw new Error("imessage_space_unavailable");
  if (action.kind === "send") return space.send(action.body);
  if (action.kind === "image") {
    if (!media?.data?.length || !IMAGE_TYPES.has(media.mimeType)) throw new Error("imessage_image_unavailable");
    return space.send(builders.attachment(media.data, { mimeType: media.mimeType, name: "connie-image." + ({ "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif" }[media.mimeType]) }));
  }
  const target = await space.getMessage(action.ref_id);
  if (!target || target.id !== action.ref_id || target.space?.id !== action.chat_guid) {
    throw new Error("imessage_target_unavailable");
  }
  if (action.kind === "reply") return space.send(builders.reply(builders.text(action.body), target));
  if (action.kind === "reaction") return space.send(builders.reaction(action.body, target));
  throw new Error("imessage_action_unsupported");
}


// Only SDK-owned attachment streams are read. Never fetch a sender-supplied URL.
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);
function imageAttachments(content, depth = 0) {
  if (!content || depth > 8) return [];
  if (content.type === "attachment" && content.mimeType?.startsWith("image/")) return [content];
  if (content.type === "reply") return imageAttachments(content.content, depth + 1);
  if (content.type === "group") return (content.items || []).flatMap(item => imageAttachments(item.content, depth + 1));
  return [];
}

async function boundedImage(attachment, remaining) {
  if (!IMAGE_TYPES.has(attachment.mimeType)) throw new Error("图片格式暂不支持，请改发 JPEG、PNG、GIF 或 WebP");
  if (attachment.size > remaining) throw new Error("图片总大小超过 8MB");
  let reader;
  let timer;
  const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("download_timeout")), 15000); });
  const chunks = [];
  let size = 0;
  try {
    reader = (await Promise.race([attachment.stream(), timeout])).getReader();
    while (true) {
      const { done, value } = await Promise.race([reader.read(), timeout]);
      if (done) break;
      const chunk = Buffer.from(value);
      size += chunk.length;
      if (size > remaining) throw new Error("图片总大小超过 8MB");
      chunks.push(chunk);
    }
    if (!size) throw new Error("图片为空");
    return { data: `data:${attachment.mimeType};base64,${Buffer.concat(chunks).toString("base64")}`, size };
  } finally {
    clearTimeout(timer);
    if (reader) {
      // Cancellation must not hold up all subsequent incoming messages.
      void reader.cancel().catch(() => {});
      reader.releaseLock();
    }
  }
}

export async function normalizeInboundWithImages(message, fallbackSpace = "", ownerPhone = "") {
  // Reject unknown senders before downloading their media.
  const phone = value => String(value || "").replace(/[^0-9]/g, "");
  if (!phone(ownerPhone) || phone(message.sender?.id) !== phone(ownerPhone)) return null;
  const payload = normalizeInbound(message, fallbackSpace, true);
  if (!payload || payload.kind === "reaction") return payload;
  const attachments = imageAttachments(message.content);
  if (!attachments.length) return payload;
  payload.images = [];
  let size = 0;
  try {
    if (attachments.length > 4) throw new Error("单条消息最多支持 4 张图片，请分开发送");
    for (const attachment of attachments) {
      const result = await boundedImage(attachment, MAX_IMAGE_BYTES - size);
      payload.images.push(result.data);
      size += result.size;
    }
  } catch (error) {
    // Keep the accompanying text but do not imply a partially read album was seen.
    payload.images = [];
    const known = ["图片格式暂不支持，请改发 JPEG、PNG、GIF 或 WebP", "图片总大小超过 8MB", "图片为空", "单条消息最多支持 4 张图片，请分开发送"];
    const reason = known.includes(error.message) ? error.message : "图片下载失败，请重新发送";
    payload.text = `${payload.text || ""}\n[桥接附件状态：${reason}；本条图片未提供给模型]`.trim();
  }
  return payload;
}
