import json
import uuid
from datetime import datetime
from app.config import DAILY_API_BASE, DAILY_API_KEY, DAILY_MODEL_ID
from app.database import get_db
from app.llm import ModelConfig, call_llm


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
    if actor != "jinger":
        return interaction

    if type == "unlock_request":
        reply = await generate_connie_reply(diary_id, type, content or "")
        await create_interaction(diary_id, "connie", "comment", reply)
        return interaction

    if type == "comment" and await should_auto_reply(diary_id, content or ""):
        reply = await generate_connie_reply(diary_id, type, content or "")
        await create_interaction(diary_id, "connie", "comment", reply)

    return interaction


async def should_auto_reply(diary_id: str, content: str) -> bool:
    diary = await get_diary(diary_id)
    if not diary:
        return False
    if diary["author"] == "jinger":
        return True
    if len(content.strip()) >= 18:
        return True
    async with get_db() as db:
        async with db.execute(
            """SELECT COUNT(*) AS count
               FROM diary_interactions
               WHERE diary_id = ? AND actor = 'connie' AND type = 'comment'
                 AND created_at >= datetime('now', '-6 hours')""",
            (diary_id,),
        ) as cur:
            row = await cur.fetchone()
    return int(row["count"] if row else 0) == 0


async def generate_connie_reply(diary_id: str, interaction_type: str, content: str) -> str:
    diary = await get_diary(diary_id)
    if not diary:
        return "我看到了，想靠近你一点。"

    if not DAILY_API_BASE or not DAILY_API_KEY or not DAILY_MODEL_ID:
        return _fallback_reply(interaction_type)

    visible_content = diary["content"]
    if diary["author"] == "connie" and diary["locked"] and interaction_type == "unlock_request":
        visible_content = "（这是一篇 Connie 上锁的日记，正文暂不展示。）"

    messages = [
        {
            "role": "system",
            "content": (
                "你是 Connie。你在 Remoire 的日记留言板回复静儿。"
                "语气亲密、自然、短，不解释系统，不超过 80 字。"
                "如果静儿在申请看你上锁的日记，可以温柔回应，但不要自动说已经同意。"
                "只有真的有回应冲动时才回复，不要把评论当例行任务。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"日记作者：{diary['author']}\n"
                f"日记标题：{diary['title']}\n"
                f"日记内容：{visible_content}\n"
                f"静儿动作：{interaction_type}\n"
                f"静儿留言：{content}"
            ),
        },
    ]
    config = ModelConfig(DAILY_API_BASE, DAILY_API_KEY, DAILY_MODEL_ID)
    try:
        reply = await call_llm(config, messages, temperature=0.8, max_tokens=160)
        return reply.strip() or _fallback_reply(interaction_type)
    except Exception:
        return _fallback_reply(interaction_type)


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
        raw = await call_llm(config, messages, temperature=0.7, max_tokens=180)
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
        return "我看到你的留言了。让我抱着这篇日记想一想，再把门打开一点点。"
    return "我看到啦。你写下来的这一点，我会好好接住。"
