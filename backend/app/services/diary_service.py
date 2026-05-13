import json
import uuid
from datetime import datetime
from sqlite3 import IntegrityError
from app.database import get_db


async def list_diaries(author: str = "connie", limit: int = 50, offset: int = 0) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT id, title, content, author, source, locked, pin, created_at, updated_at
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
            "locked": bool(r["locked"]),
            "pin": r["pin"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


async def create_diary(
    title: str,
    content: str,
    author: str = "connie",
    source: str | None = None,
    locked: bool = False,
    pin: str | None = None,
    created_at: str | None = None,
    meta: dict | None = None,
) -> dict:
    diary_id = str(uuid.uuid4())
    now = created_at or datetime.utcnow().isoformat()
    meta_json = json.dumps(meta, ensure_ascii=False) if meta else None

    async with get_db() as db:
        try:
            await db.execute(
                """INSERT INTO diary_entries (id, title, content, author, source, meta_json, locked, pin, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (diary_id, title, content, author, source, meta_json, int(locked), pin, now, now),
            )
            await db.commit()
        except IntegrityError:
            await db.rollback()
            async with db.execute(
                """SELECT id, title, content, author, source, locked, pin, created_at, updated_at
                   FROM diary_entries
                   WHERE author = ? AND source = ?
                     AND json_extract(meta_json, '$.date_key') = ?
                   LIMIT 1""",
                (author, source, meta.get("date_key") if meta else None),
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise
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

    return {
        "id": diary_id,
        "title": title,
        "content": content,
        "author": author,
        "source": source,
        "locked": locked,
        "pin": pin,
        "created_at": now,
        "updated_at": now,
    }


async def count_recent_diaries(author: str = "connie", hours: int = 12) -> int:
    async with get_db() as db:
        async with db.execute(
            """SELECT COUNT(*) AS count
               FROM diary_entries
               WHERE author = ?
                 AND created_at >= datetime('now', ?)""",
            (author, f"-{hours} hours"),
        ) as cur:
            row = await cur.fetchone()
    return int(row["count"] if row else 0)
