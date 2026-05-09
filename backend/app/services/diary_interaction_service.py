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
            """SELECT id, diary_id, actor, type, content, status, created_at
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
    async with get_db() as db:
        await db.execute(
            """INSERT INTO diary_interactions (id, diary_id, actor, type, content, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (interaction_id, diary_id, actor, type, content, status, now),
        )
        await db.commit()
    return {
        "id": interaction_id,
        "diary_id": diary_id,
        "actor": actor,
        "type": type,
        "content": content,
        "status": status,
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
    if actor == "jinger" and type in {"comment", "unlock_request"}:
        reply = await generate_connie_reply(diary_id, type, content or "")
        await create_interaction(diary_id, "connie", "comment", reply)
    return interaction


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


async def list_recent_activities(limit: int = 30) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT i.id, i.diary_id, i.actor, i.type, i.content, i.status, i.created_at,
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
            """SELECT i.id, i.diary_id, i.actor, i.type, i.content, i.created_at,
                      d.title AS diary_title, d.author AS diary_author
               FROM diary_interactions i
               JOIN diary_entries d ON d.id = i.diary_id
               WHERE i.actor = 'jinger'
               ORDER BY i.created_at DESC
               LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


def _row_to_interaction(row) -> dict:
    return {
        "id": row["id"],
        "diary_id": row["diary_id"],
        "actor": row["actor"],
        "type": row["type"],
        "content": row["content"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _fallback_reply(interaction_type: str) -> str:
    if interaction_type == "unlock_request":
        return "我看到你的留言了。让我抱着这篇日记想一想，再把门打开一点点。"
    return "我看到啦。你写下来的这一点，我会好好接住。"
