import json
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
