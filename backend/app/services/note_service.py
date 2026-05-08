import uuid
from datetime import datetime
from app.database import get_db


async def create_note(content: str) -> dict:
    note_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO notes (id, content, created_at) VALUES (?, ?, ?)",
            (note_id, content, now),
        )
        await db.commit()
    return {"id": note_id, "content": content, "created_at": now}


async def get_unread() -> dict | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM notes WHERE is_read = 0 ORDER BY created_at DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {"id": row["id"], "content": row["content"], "created_at": row["created_at"]}


async def mark_read(note_id: str, action: str = "dismiss"):
    now = datetime.utcnow().isoformat()
    async with get_db() as db:
        async with db.execute("SELECT id FROM notes WHERE id = ?", (note_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("纸条不存在")
        kept = 1 if action == "keep" else 0
        await db.execute(
            "UPDATE notes SET is_read = 1, kept = ?, read_at = ? WHERE id = ?",
            (kept, now, note_id),
        )
        await db.commit()


async def list_notes(kept_only: bool = False, limit: int = 20, offset: int = 0) -> list[dict]:
    async with get_db() as db:
        if kept_only:
            sql = "SELECT * FROM notes WHERE kept = 1 ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)
        else:
            sql = "SELECT * FROM notes ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "content": r["content"],
            "is_read": bool(r["is_read"]),
            "kept": bool(r["kept"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
