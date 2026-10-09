"""iMessage text shaping. No database, no model calls."""

import random
import re

INGRESS_NOTE = "静儿这条消息来自 iMessage，不是网页。"
FAILURE_PHRASE = "我这边信号有点卡，等我一下"
NUDGE_CHANNEL_NOTE = "（如果这次你决定发消息，这条会发到 iMessage。）"

_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"(\*\*|__)")
_CODE = re.compile(r"`+")
_HEADING = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_BANNER = re.compile(r"正在查记忆|正在使用工具|工具调用|tool_start|ToolCall")


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    return f"+{digits}" if digits else ""


def label_history_content(content: str, channel: str | None) -> str:
    text = content or ""
    if text.startswith("【来自 "):
        end = text.find("】")
        if end != -1:
            text = text[end + 1 :].lstrip()
    return text


def sanitize_bubbles(text: str) -> list[str]:
    cleaned = _LINK.sub(r"\1", text or "")
    cleaned = _BOLD.sub("", cleaned)
    cleaned = _CODE.sub("", cleaned)
    cleaned = _HEADING.sub("", cleaned)
    cleaned = _BANNER.sub("", cleaned)
    parts = []
    for block in re.split(r"\n\s*\n", cleaned):
        line = block.strip()
        if line:
            parts.append(line)
    return parts


def sanitize_imessage_text(text: str) -> str:
    return "\n\n".join(sanitize_bubbles(text))


def bubble_delay_ms(text: str, ms_per_char: int, *, first: bool, roll: float | None = None) -> int:
    if first:
        return 0
    jitter = int((random.random() if roll is None else roll) * 400)
    raw = len(text) * max(1, ms_per_char) + jitter
    return max(800, min(6000, raw))
