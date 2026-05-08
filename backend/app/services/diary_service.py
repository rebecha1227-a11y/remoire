import uuid
from datetime import datetime
from app.database import get_db


async def list_diaries(author: str = "connie", limit: int = 50, offset: int = 0) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT id, title, content, author, source, created_at, updated_at
               FROM diary_entries
               WHERE author = ?
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (author, limit, offset),
        ) as cur:
            rows = await cur.fetchall()

    return [
        {
            "id": r["id"],
            "title": r["title"],
            "content": r["content"],
            "author": r["author"],
            "source": r["source"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


async def create_diary(title: str, content: str, author: str = "connie", source: str | None = None) -> dict:
    diary_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    async with get_db() as db:
        await db.execute(
            """INSERT INTO diary_entries (id, title, content, author, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (diary_id, title, content, author, source, now, now),
        )
        await db.commit()

    return {
        "id": diary_id,
        "title": title,
        "content": content,
        "author": author,
        "source": source,
        "created_at": now,
        "updated_at": now,
    }
