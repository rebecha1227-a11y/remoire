import json
import math
from datetime import datetime, timezone

from app.database import get_db
from app.llm import call_llm
from app.services import model_settings_service


SUMMARY_VERSION = 1
SUMMARY_TRIGGER_MESSAGES = 28
SUMMARY_TRIGGER_TOKENS = 10000
SUMMARY_KEEP_MESSAGES = 12
SUMMARY_CHUNK_MESSAGES = 60
SUMMARY_MAX_OUTPUT = 1400
IMAGE_TOKEN_RESERVE = 1600


class ContextBudgetError(ValueError):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


def estimate_text_tokens(text: str | None) -> int:
    """Conservative tokenizer-independent estimate for mixed Chinese and Latin text."""
    if not text:
        return 0
    cjk_or_wide = 0
    compact = 0
    for char in str(text):
        code = ord(char)
        if (
            0x3400 <= code <= 0x9FFF
            or 0xF900 <= code <= 0xFAFF
            or 0x3040 <= code <= 0x30FF
            or code >= 0x1F000
        ):
            cjk_or_wide += 1
        else:
            compact += 1
    return max(1, cjk_or_wide + math.ceil(compact / 4))


def estimate_content_tokens(content) -> int:
    if isinstance(content, str):
        return estimate_text_tokens(content)
    if not isinstance(content, list):
        return estimate_text_tokens(json.dumps(content, ensure_ascii=False, default=str))
    total = 0
    for part in content:
        if not isinstance(part, dict):
            total += estimate_text_tokens(str(part))
        elif part.get("type") == "image_url":
            total += IMAGE_TOKEN_RESERVE
        else:
            total += estimate_text_tokens(part.get("text") or part.get("content") or "")
    return total


def estimate_message_tokens(message: dict) -> int:
    total = 6 + estimate_text_tokens(message.get("role", ""))
    total += estimate_content_tokens(message.get("content", ""))
    if message.get("tool_calls"):
        total += estimate_text_tokens(json.dumps(message["tool_calls"], ensure_ascii=False, default=str))
    total += estimate_text_tokens(message.get("tool_call_id", ""))
    return total


def estimate_messages_tokens(messages: list[dict]) -> int:
    return 3 + sum(estimate_message_tokens(message) for message in messages)


def estimate_tools_tokens(tools: list[dict] | None) -> int:
    if not tools:
        return 0
    return 12 + estimate_text_tokens(json.dumps(tools, ensure_ascii=False, separators=(",", ":")))


def input_token_budget(context_window: int, output_budget: int) -> int:
    safety = max(512, min(4096, int(context_window * 0.04)))
    result = context_window - output_budget - safety
    if result < 1024:
        raise ContextBudgetError(
            "模型的上下文窗口不足以同时容纳输入、输出和安全余量。",
            details={"context_window": context_window, "output_budget": output_budget, "safety": safety},
        )
    return result


def truncate_text_to_tokens(text: str, max_tokens: int, marker: str = "\n[…内容因上下文预算省略…]") -> str:
    if max_tokens <= 0:
        return ""
    if estimate_text_tokens(text) <= max_tokens:
        return text
    marker_tokens = estimate_text_tokens(marker)
    if marker_tokens >= max_tokens:
        return marker[: max(1, max_tokens)]
    low, high = 0, len(text)
    target = max_tokens - marker_tokens
    while low < high:
        mid = (low + high + 1) // 2
        if estimate_text_tokens(text[:mid]) <= target:
            low = mid
        else:
            high = mid - 1
    return text[:low].rstrip() + marker


async def get_conversation_summary(conversation_id: str) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            """SELECT conversation_id, summary, through_message_rowid, through_message_id,
                      source_message_count, version, updated_at
               FROM conversation_summaries WHERE conversation_id = ?""",
            (conversation_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def get_history_after_summary(
    conversation_id: str,
    through_message_rowid: int = 0,
    limit: int = 240,
) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT rowid AS message_rowid, id, role, content, thinking, image,
                      display_mode, created_at
               FROM messages
               WHERE conversation_id = ? AND rowid > ?
               ORDER BY rowid DESC LIMIT ?""",
            (conversation_id, through_message_rowid, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


async def maybe_compact_conversation(conversation_id: str) -> bool:
    """Summarize one contiguous old range and advance its exact coverage marker."""
    current = await get_conversation_summary(conversation_id)
    through = int(current["through_message_rowid"]) if current else 0
    async with get_db() as db:
        async with db.execute(
            """SELECT rowid AS message_rowid, id, role, content, created_at
               FROM messages WHERE conversation_id = ? AND rowid > ?
               ORDER BY rowid ASC""",
            (conversation_id, through),
        ) as cursor:
            rows = [dict(row) for row in await cursor.fetchall()]

    raw_tokens = sum(estimate_text_tokens(row["content"]) + 12 for row in rows)
    if len(rows) <= SUMMARY_KEEP_MESSAGES:
        return False
    if len(rows) <= SUMMARY_TRIGGER_MESSAGES and raw_tokens <= SUMMARY_TRIGGER_TOKENS:
        return False
    compress_count = min(len(rows) - SUMMARY_KEEP_MESSAGES, SUMMARY_CHUNK_MESSAGES)
    source_rows = rows[:compress_count]
    if not source_rows:
        return False

    config, slot = await model_settings_service.get_model_config_for_slot("backend")
    context_window = int(slot.get("context_window") or model_settings_service.DEFAULT_CONTEXT_WINDOW)
    output_budget = min(
        int(slot.get("output_budget") or model_settings_service.DEFAULT_OUTPUT_BUDGET),
        SUMMARY_MAX_OUTPUT,
    )
    max_input = input_token_budget(context_window, output_budget)
    system = (
        "你在压缩一段两人关系中的旧聊天记录，供未来对话恢复上下文。"
        "只保留原文支持的事实、关系变化、情绪脉络、承诺、未完成话题、称呼与近期状态；"
        "保留时间和不确定性，不补写、不推断。助手说过的话不能自动当成用户事实。"
        "摘要只是对话索引，不是长期记忆，也不能据此新建记忆。使用简体中文，正文直接开始。"
    )

    def source_text(selected: list[dict]) -> str:
        lines = []
        if current and current.get("summary"):
            lines.append("【此前摘要】\n" + current["summary"])
        lines.append("【本次连续覆盖的原始消息】")
        for row in selected:
            lines.append(
                f"[{row['message_rowid']} | {row['created_at']} | {row['role']}]\n{row['content']}"
            )
        return "\n\n".join(lines)

    while source_rows:
        candidate = [{"role": "system", "content": system}, {"role": "user", "content": source_text(source_rows)}]
        if estimate_messages_tokens(candidate) <= max_input:
            break
        source_rows.pop()
    if not source_rows:
        return False

    summary = (await call_llm(
        config,
        [{"role": "system", "content": system}, {"role": "user", "content": source_text(source_rows)}],
        temperature=0.2,
        max_tokens=output_budget,
    )).strip()
    if not summary:
        return False

    target = source_rows[-1]
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        if current:
            cursor = await db.execute(
                """UPDATE conversation_summaries
                   SET summary = ?, through_message_rowid = ?, through_message_id = ?,
                       source_message_count = ?, version = ?, updated_at = ?
                   WHERE conversation_id = ? AND version = ? AND through_message_rowid = ?""",
                (
                    summary,
                    target["message_rowid"],
                    target["id"],
                    int(current["source_message_count"]) + len(source_rows),
                    int(current["version"]) + 1,
                    now,
                    conversation_id,
                    current["version"],
                    through,
                ),
            )
        else:
            cursor = await db.execute(
                """INSERT OR IGNORE INTO conversation_summaries
                   (conversation_id, summary, through_message_rowid, through_message_id,
                    source_message_count, version, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    conversation_id,
                    summary,
                    target["message_rowid"],
                    target["id"],
                    len(source_rows),
                    SUMMARY_VERSION,
                    now,
                ),
            )
        changed = cursor.rowcount == 1
        if changed:
            await db.commit()
        else:
            await db.rollback()
    return changed
