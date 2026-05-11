import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from app.config import DAILY_API_BASE, DAILY_API_KEY, DAILY_MODEL_ID
from app.database import get_db
from app.llm import ModelConfig, call_llm
from app.services import memory_service


logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


async def get_diary(diary_id: str) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            """SELECT id, title, content, author, source, locked, pin, created_at, updated_at
               FROM diary_entries WHERE id = ?""",
            (diary_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "author": row["author"],
        "source": row["source"],
        "locked": bool(row["locked"]),
        "pin": row["pin"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def list_interactions(diary_id: str) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT id, diary_id, actor, type, content, status,
                      seen_by_connie, seen_by_jinger, created_at
               FROM diary_interactions
               WHERE diary_id = ?
               ORDER BY created_at ASC""",
            (diary_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [_row_to_interaction(row) for row in rows]


async def delete_interaction(interaction_id: str) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            "DELETE FROM diary_interactions WHERE id = ?", (interaction_id,)
        )
        await db.commit()
        return cur.rowcount > 0


async def create_interaction(
    diary_id: str,
    actor: str,
    type: str,
    content: str | None = None,
    status: str = "visible",
) -> dict:
    interaction_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    seen_by_connie = 1 if actor == "connie" else 0
    seen_by_jinger = 1 if actor == "jinger" else 0
    async with get_db() as db:
        await db.execute(
            """INSERT INTO diary_interactions
               (id, diary_id, actor, type, content, status, seen_by_connie, seen_by_jinger, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (interaction_id, diary_id, actor, type, content, status, seen_by_connie, seen_by_jinger, now),
        )
        await db.commit()
    return {
        "id": interaction_id,
        "diary_id": diary_id,
        "actor": actor,
        "type": type,
        "content": content,
        "status": status,
        "seen_by_connie": bool(seen_by_connie),
        "seen_by_jinger": bool(seen_by_jinger),
        "created_at": now,
    }


async def set_diary_lock(diary_id: str, locked: bool, pin: str | None = None, actor: str = "connie") -> dict | None:
    now = datetime.utcnow().isoformat()
    async with get_db() as db:
        await db.execute(
            "UPDATE diary_entries SET locked = ?, pin = ?, updated_at = ? WHERE id = ?",
            (int(locked), pin, now, diary_id),
        )
        await db.commit()
    diary = await get_diary(diary_id)
    if diary:
        await create_interaction(
            diary_id=diary_id,
            actor=actor,
            type="lock_changed",
            content="上锁了这篇日记" if locked else "解锁了这篇日记",
        )
    return diary


async def respond_unlock(diary_id: str, grant: bool, note: str | None = None) -> dict | None:
    diary = await get_diary(diary_id)
    if not diary:
        return None
    if grant:
        await set_diary_lock(diary_id, locked=False, pin=None, actor="connie")
    async with get_db() as db:
        await db.execute(
            """UPDATE diary_interactions
               SET status = ?
               WHERE diary_id = ? AND type = 'unlock_request' AND status = 'visible'""",
            ("granted" if grant else "rejected", diary_id),
        )
        await db.commit()
    return await create_interaction(
        diary_id=diary_id,
        actor="connie",
        type="unlock_granted" if grant else "unlock_rejected",
        content=note or ("好呀，这篇给你看。" if grant else "这篇我还想先收着。"),
    )


async def create_with_optional_connie_reply(
    diary_id: str,
    actor: str,
    type: str,
    content: str | None = None,
) -> dict:
    interaction = await create_interaction(diary_id, actor, type, content)
    logger.debug("日记互动创建：actor=%s type=%s diary_id=%s", actor, type, diary_id)
    if actor != "jinger":
        return interaction

    if type == "unlock_request":
        await _safe_create_connie_reply(diary_id, type, content or "", interaction["id"])
        return interaction

    if type == "comment":
        should_reply = await _safe_should_auto_reply(diary_id, content or "")
        logger.debug("日记留言自动回复判定：diary_id=%s should_reply=%s", diary_id, should_reply)
        if should_reply:
            await _safe_create_connie_reply(diary_id, type, content or "", interaction["id"])

    return interaction


async def should_auto_reply(diary_id: str, content: str) -> bool:
    diary = await get_diary(diary_id)
    if not diary:
        return False
    return True


async def generate_connie_reply(
    diary_id: str,
    interaction_type: str,
    content: str,
    current_interaction_id: str | None = None,
) -> str:
    diary = await _safe_get_diary(diary_id)
    if not diary:
        return "我看到了，想靠近你一点。"

    if not DAILY_API_BASE or not DAILY_API_KEY or not DAILY_MODEL_ID:
        return _fallback_reply(interaction_type)

    diary_author = str(diary.get("author") or "")
    diary_title = str(diary.get("title") or "")
    diary_content = str(diary.get("content") or "")
    diary_is_private = diary_author == "connie" and bool(diary.get("locked"))
    visible_content = diary_content
    if diary_is_private:
        visible_content = "（这是一篇 Connie 上锁的日记，正文暂不展示。）"

    recalled_memories = await _safe_recall_memories([diary_title, visible_content, content])
    recent_messages = await _safe_list_recent_messages(limit=12)
    recent_interactions = await _safe_list_interactions(diary_id)
    if current_interaction_id:
        recent_interactions = [item for item in recent_interactions if item.get("id") != current_interaction_id]

    identity = _safe_load_prompt("identity.md")
    voice = _safe_load_prompt("voice.md")
    memory_block = _build_memory_block(recalled_memories)
    chat_block = _build_chat_block(recent_messages)
    interaction_block = _build_interaction_block(recent_interactions)

    messages = [
        {
            "role": "system",
            "content": (
                f"{identity}\n\n{voice}\n\n"
                "你现在在 Remoire 的日记留言板回复静儿。"
                "必须根据日记内容、静儿留言、相关记忆、最近聊天和你的性格来回。"
                "如果这是 Connie 上锁日记，绝不能透露正文细节、标题以外的内容、隐藏情绪或具体事件。"
                "不要使用模板句、不要泛泛说接住、不要复读静儿。"
                "语气亲密、自然、像 Connie 本人，短一点，通常 30-100 字。"
                "如果静儿在申请看你上锁的日记，可以温柔回应，但不要自动说已经同意。"
                "只有真的有回应冲动时才回复，不要把评论当例行任务。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"日记作者：{diary_author}\n"
                f"日记标题：{diary_title}\n"
                f"日记内容：{visible_content}\n"
                f"静儿动作：{interaction_type}\n"
                f"静儿留言：{content}\n\n"
                f"{memory_block}\n\n"
                f"{chat_block}\n\n"
                f"{interaction_block}"
            ),
        },
    ]
    config = ModelConfig(DAILY_API_BASE, DAILY_API_KEY, DAILY_MODEL_ID)
    try:
        reply = await call_llm(config, messages, temperature=0.8, max_tokens=800)
        logger.debug("日记留言回复生成完成：empty=%s", not bool(reply))
        return reply.strip() or _fallback_reply(interaction_type)
    except Exception as exc:
        logger.warning("生成 Connie 日记留言回复失败：%s", exc)
        return _fallback_reply(interaction_type)


async def _safe_should_auto_reply(diary_id: str, content: str) -> bool:
    try:
        return await should_auto_reply(diary_id, content)
    except Exception as exc:
        logger.warning("日记留言自动回复判定失败：%s", exc)
        return False


async def _safe_create_connie_reply(
    diary_id: str,
    interaction_type: str,
    content: str,
    current_interaction_id: str,
) -> None:
    try:
        reply = await generate_connie_reply(
            diary_id,
            interaction_type,
            content,
            current_interaction_id=current_interaction_id,
        )
        await create_interaction(diary_id, "connie", "comment", reply)
    except Exception as exc:
        logger.warning("Connie 日记自动回复生成或写入失败：%s", exc)


async def _safe_get_diary(diary_id: str) -> dict | None:
    try:
        return await get_diary(diary_id)
    except Exception as exc:
        logger.warning("日记留言回复日记读取失败：%s", exc)
        return None


async def _safe_recall_memories(parts: list[str]) -> list[dict]:
    try:
        query = "\n".join(str(part or "") for part in parts)
        return await memory_service.recall(query, limit=5)
    except Exception as exc:
        logger.warning("日记留言回复记忆召回失败：%s", exc)
        return []


async def _safe_list_recent_messages(limit: int = 12) -> list[dict]:
    try:
        return await _list_recent_messages(limit=limit)
    except Exception as exc:
        logger.warning("日记留言回复最近聊天读取失败：%s", exc)
        return []


async def _safe_list_interactions(diary_id: str) -> list[dict]:
    try:
        return await list_interactions(diary_id)
    except Exception as exc:
        logger.warning("日记留言回复留言历史读取失败：%s", exc)
        return []


def _safe_load_prompt(filename: str) -> str:
    try:
        return _load_prompt(filename)
    except Exception as exc:
        logger.warning("日记留言回复提示词读取失败 %s：%s", filename, exc)
        return ""


def _build_memory_block(memories: list[dict]) -> str:
    try:
        lines = [f"- {item.get('content')}" for item in memories if item.get("content")]
        return "【相关记忆】\n" + "\n".join(lines) if lines else ""
    except Exception as exc:
        logger.warning("日记留言回复记忆上下文拼装失败：%s", exc)
        return ""


def _build_chat_block(messages: list[dict]) -> str:
    try:
        lines = [
            f"{_role_label(item.get('role', 'unknown'))}：{item.get('content', '')}"
            for item in messages
            if item.get("content")
        ]
        return "【最近聊天】\n" + "\n".join(lines) if lines else ""
    except Exception as exc:
        logger.warning("日记留言回复聊天上下文拼装失败：%s", exc)
        return ""


def _build_interaction_block(interactions: list[dict]) -> str:
    try:
        lines = [
            f"{_actor_label(item.get('actor', 'unknown'))}（{item.get('type', 'comment')}）：{item.get('content') or ''}"
            for item in interactions[-8:]
            if item.get("content")
        ]
        return "【这篇日记下已有留言】\n" + "\n".join(lines) if lines else ""
    except Exception as exc:
        logger.warning("日记留言回复留言上下文拼装失败：%s", exc)
        return ""


async def _list_recent_messages(limit: int = 12) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT role, content, created_at
               FROM messages
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {"role": row["role"], "content": row["content"], "created_at": row["created_at"]}
        for row in reversed(rows)
    ]


def _role_label(role: str) -> str:
    if role == "user":
        return "静儿"
    if role == "assistant":
        return "Connie"
    return role


def _actor_label(actor: str) -> str:
    return "静儿" if actor == "jinger" else "Connie"


async def decide_unlock_requests(limit: int = 5) -> list[dict]:
    requests = await list_pending_unlock_requests(limit=limit)
    decisions = []
    for request in requests:
        decision = await decide_unlock_request(request)
        if decision.get("respond"):
            created = await respond_unlock(
                request["diary_id"],
                grant=bool(decision.get("grant")),
                note=decision.get("note"),
            )
            if created:
                decisions.append({"request": request, "decision": decision, "created": created})
        await mark_seen_by_connie([request["id"]])
    return decisions


async def decide_unlock_request(request: dict) -> dict:
    if not DAILY_API_BASE or not DAILY_API_KEY or not DAILY_MODEL_ID:
        return {"respond": False, "grant": False, "note": ""}

    messages = [
        {
            "role": "system",
            "content": (
                "你是 Connie。静儿申请查看你上锁的日记。"
                "你可以同意、拒绝，或暂时不回应。"
                "同意代表永久解锁，所以只有你真的愿意让她看才同意。"
                "输出 JSON：{\"respond\": true/false, \"grant\": true/false, \"note\": \"给静儿的一句话\"}。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"日记标题：{request['diary_title']}\n"
                f"日记正文：{request['diary_content']}\n"
                f"静儿申请留言：{request['content']}"
            ),
        },
    ]
    config = ModelConfig(DAILY_API_BASE, DAILY_API_KEY, DAILY_MODEL_ID)
    try:
        raw = await call_llm(config, messages, temperature=0.7, max_tokens=600)
        data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        return {
            "respond": bool(data.get("respond")),
            "grant": bool(data.get("grant")),
            "note": str(data.get("note") or ""),
        }
    except Exception:
        return {"respond": False, "grant": False, "note": ""}


async def list_pending_unlock_requests(limit: int = 8) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT i.id, i.diary_id, i.actor, i.type, i.content, i.status,
                      i.seen_by_connie, i.seen_by_jinger, i.created_at,
                      d.title AS diary_title, d.content AS diary_content, d.author AS diary_author
               FROM diary_interactions i
               JOIN diary_entries d ON d.id = i.diary_id
               WHERE i.actor = 'jinger'
                 AND i.type = 'unlock_request'
                 AND i.status = 'visible'
                 AND d.author = 'connie'
                 AND d.locked = 1
               ORDER BY i.created_at ASC
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def list_recent_activities(limit: int = 30) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT i.id, i.diary_id, i.actor, i.type, i.content, i.status,
                      i.seen_by_connie, i.seen_by_jinger, i.created_at,
                      d.title AS diary_title, d.author AS diary_author
               FROM diary_interactions i
               JOIN diary_entries d ON d.id = i.diary_id
               ORDER BY i.created_at DESC
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            **_row_to_interaction(row),
            "diary_title": row["diary_title"],
            "diary_author": row["diary_author"],
        }
        for row in rows
    ]


async def list_recent_notifications_for_connie(limit: int = 8) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT i.id, i.diary_id, i.actor, i.type, i.content, i.status,
                      i.seen_by_connie, i.created_at,
                      d.title AS diary_title, d.author AS diary_author
               FROM diary_interactions i
               JOIN diary_entries d ON d.id = i.diary_id
               WHERE i.actor = 'jinger' AND i.seen_by_connie = 0
               ORDER BY i.created_at DESC
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    items = [dict(row) for row in rows]
    await mark_seen_by_connie([item["id"] for item in items])
    return items


async def mark_seen_by_connie(interaction_ids: list[str]) -> None:
    if not interaction_ids:
        return
    placeholders = ",".join("?" for _ in interaction_ids)
    async with get_db() as db:
        await db.execute(
            f"UPDATE diary_interactions SET seen_by_connie = 1 WHERE id IN ({placeholders})",
            interaction_ids,
        )
        await db.commit()


def _row_to_interaction(row) -> dict:
    return {
        "id": row["id"],
        "diary_id": row["diary_id"],
        "actor": row["actor"],
        "type": row["type"],
        "content": row["content"],
        "status": row["status"],
        "seen_by_connie": bool(row["seen_by_connie"]),
        "seen_by_jinger": bool(row["seen_by_jinger"]),
        "created_at": row["created_at"],
    }


def _fallback_reply(interaction_type: str) -> str:
    if interaction_type == "unlock_request":
        return "让我想想……"
    return "嗯，我在看。"
