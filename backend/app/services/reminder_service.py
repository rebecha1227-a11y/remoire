import json
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path

from app.database import get_db
from app.llm import call_llm
from app.services import model_settings_service

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "reminder_extract.md"


def _load_prompt():
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return None


def _bj_now():
    return datetime.utcnow() + timedelta(hours=8)


async def extract_reminders(conversation_id: str, messages: list[dict]):
    prompt = _load_prompt()
    if not prompt:
        return []

    now = _bj_now()
    chat_text = f"当前时间：{now.strftime('%Y-%m-%d %H:%M')}（北京时间）\n\n"
    chat_text += "\n".join(
        f"{'静儿' if m['role'] == 'user' else 'Connie'}: {m['content']}"
        for m in messages
    )

    config, slot_settings = await model_settings_service.get_model_config_for_slot("backend")
    raw = await call_llm(
        config,
        [{"role": "system", "content": prompt}, {"role": "user", "content": chat_text}],
        stream=False,
        temperature=0.2,
        max_tokens=1000,
        extended_thinking=bool(slot_settings.get("extended_thinking")),
    )

    content = raw if isinstance(raw, str) else raw.get("content", "")
    logger.info("待办提取 LLM 原始返回: %s", content[:500])
    try:
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(content[start:end])
        else:
            items = []
    except (json.JSONDecodeError, ValueError):
        logger.warning("待办提取 JSON 解析失败: %s", content[:200])
        items = []

    logger.info("待办提取结果: %d 条", len(items))
    saved = []
    for item in items:
        if not item.get("content") or not item.get("remind_at"):
            continue
        if await _is_duplicate(item["content"], item["remind_at"]):
            continue
        reminder = await create_reminder(
            content=item["content"],
            remind_at=item["remind_at"],
            conversation_id=conversation_id,
            urgent=item.get("urgent", False),
        )
        saved.append(reminder)

    return saved


async def _is_duplicate(content: str, remind_at: str) -> bool:
    async with get_db() as db:
        async with db.execute(
            "SELECT 1 FROM reminders WHERE content = ? AND remind_at = ? AND status != 'dismissed' LIMIT 1",
            (content, remind_at),
        ) as cur:
            return await cur.fetchone() is not None


async def create_reminder(content: str, remind_at: str, conversation_id: str | None = None, urgent: bool = False) -> dict:
    rid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO reminders (id, content, remind_at, status, conversation_id, created_at) VALUES (?, ?, ?, 'pending', ?, ?)",
            (rid, content, remind_at, conversation_id, now),
        )
        await db.commit()
    return {"id": rid, "content": content, "remind_at": remind_at, "urgent": urgent, "status": "pending"}


async def list_reminders(status: str | None = "pending", limit: int = 20) -> list[dict]:
    async with get_db() as db:
        if status:
            sql = "SELECT * FROM reminders WHERE status = ? ORDER BY remind_at ASC LIMIT ?"
            params = (status, limit)
        else:
            sql = "SELECT * FROM reminders ORDER BY remind_at ASC LIMIT ?"
            params = (limit,)
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_today_reminders() -> list[dict]:
    now = _bj_now()
    today_start = now.strftime("%Y-%m-%d 00:00")
    today_end = now.strftime("%Y-%m-%d 23:59")
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM reminders WHERE status = 'pending' AND remind_at >= ? AND remind_at <= ? ORDER BY remind_at ASC",
            (today_start, today_end),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_upcoming_reminders(days: int = 7) -> list[dict]:
    now = _bj_now()
    end = (now + timedelta(days=days)).strftime("%Y-%m-%d 23:59")
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM reminders WHERE status = 'pending' AND remind_at <= ? ORDER BY remind_at ASC",
            (end,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def complete_reminder(reminder_id: str) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            "UPDATE reminders SET status = 'done' WHERE id = ? AND status = 'pending'",
            (reminder_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def dismiss_reminder(reminder_id: str) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            "UPDATE reminders SET status = 'dismissed' WHERE id = ? AND status = 'pending'",
            (reminder_id,),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_reminders_for_date(date_str: str) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM reminders WHERE remind_at >= ? AND remind_at < ? AND status != 'dismissed' ORDER BY remind_at ASC",
            (f"{date_str} 00:00", f"{date_str} 23:59"),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]
