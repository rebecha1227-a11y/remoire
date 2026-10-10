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

export function normalizeInbound(message, fallbackSpace = "") {
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
  if (!text.trim()) return null;
  return { ...base, kind: "text", text,
    reply_to: content?.type === "reply" ? String(content.target?.id || "") : "",
    quote_text: content?.type === "reply" ? textContent(content.target?.content).slice(0, 2000) : "",
  };
}

export async function sendAction(space, action, builders) {
  if (!space || space.id !== action.chat_guid) throw new Error("imessage_space_unavailable");
  if (action.kind === "send") return space.send(action.body);
  const target = await space.getMessage(action.ref_id);
  if (!target || target.id !== action.ref_id || target.space?.id !== action.chat_guid) {
    throw new Error("imessage_target_unavailable");
  }
  if (action.kind === "reply") return space.send(builders.reply(builders.text(action.body), target));
  if (action.kind === "reaction") return space.send(builders.reaction(action.body, target));
  throw new Error("imessage_action_unsupported");
}
