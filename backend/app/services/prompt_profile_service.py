"""Private, versioned relationship configuration. Drafts never enter model context."""
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_db

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
PROFILES = {
    "identity": ("身份与关系", "identity.md"),
    "voice": ("表达偏好", "voice.md"),
    "scene": ("场景写作", None),
    "original": ("原稿资料", None),
}
MAX_CONTENT = 60000


class ProfileConflict(Exception):
    pass


def _check_key(key):
    if key not in PROFILES:
        raise KeyError(key)


async def initialize(db):
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS prompt_profiles (
            key TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            content TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prompt_profile_versions (
            key TEXT NOT NULL REFERENCES prompt_profiles(key),
            version INTEGER NOT NULL,
            content TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (key, version)
        );
    """)
    # Existing DB values always win, including intentionally empty text.
    await db.execute("BEGIN IMMEDIATE")
    now = datetime.now(timezone.utc).isoformat()
    for key, (_, filename) in PROFILES.items():
        async with db.execute("SELECT 1 FROM prompt_profiles WHERE key = ?", (key,)) as cur:
            if await cur.fetchone():
                continue
        content = (PROMPTS_DIR / filename).read_text(encoding="utf-8") if filename else ""
        enabled = int(key in ("identity", "voice"))
        values = (key, 1, content, enabled, now)
        await db.execute("INSERT INTO prompt_profiles VALUES (?, ?, ?, ?, ?)", values)
        await db.execute("INSERT INTO prompt_profile_versions VALUES (?, ?, ?, ?, ?)", values)
    await db.commit()


def _serialize(row):
    return {**dict(row), "title": PROFILES[row["key"]][0], "enabled": bool(row["enabled"])}


async def list_profiles():
    async with get_db() as db:
        async with db.execute("SELECT * FROM prompt_profiles") as cur:
            rows = {row["key"]: _serialize(row) for row in await cur.fetchall()}
    return [rows[key] for key in PROFILES]


async def save_profile(key, content, enabled, expected_version):
    _check_key(key)
    if len(content) > MAX_CONTENT:
        raise ValueError("正文不能超过 60000 字符")
    enabled = bool(enabled) if key == "scene" else key in ("identity", "voice")
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM prompt_profiles WHERE key = ?", (key,)) as cur:
            old = await cur.fetchone()
        if old is None or old["version"] != expected_version:
            raise ProfileConflict("此配置已在其他页面更新，请先重新读取，再合并你的修改。")
        if old["content"] == content and bool(old["enabled"]) == enabled:
            return _serialize(old)
        version = old["version"] + 1
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE prompt_profiles SET version=?, content=?, enabled=?, updated_at=? WHERE key=?",
            (version, content, int(enabled), now, key),
        )
        await db.execute("INSERT INTO prompt_profile_versions VALUES (?, ?, ?, ?, ?)",
                         (key, version, content, int(enabled), now))
        await db.commit()
    return {"key": key, "title": PROFILES[key][0], "version": version,
            "content": content, "enabled": enabled, "updated_at": now}


async def list_versions(key, before=None, limit=20):
    _check_key(key)
    async with get_db() as db:
        async with db.execute(
            """SELECT key, version, enabled, updated_at, length(content) AS characters
               FROM prompt_profile_versions WHERE key=? AND (? IS NULL OR version < ?)
               ORDER BY version DESC LIMIT ?""", (key, before, before, limit),
        ) as cur:
            return [_serialize(row) for row in await cur.fetchall()]


async def get_version(key, version):
    _check_key(key)
    async with get_db() as db:
        async with db.execute("SELECT * FROM prompt_profile_versions WHERE key=? AND version=?",
                              (key, version)) as cur:
            row = await cur.fetchone()
    if row is None:
        raise KeyError(version)
    return _serialize(row)


async def restore_version(key, version, expected_version):
    old = await get_version(key, version)
    return await save_profile(key, old["content"], old["enabled"], expected_version)


async def load_shared(*, scene=False):
    """One DB snapshot per generation; no process cache and no original draft access."""
    profiles = await load_runtime_profiles()
    parts = [profiles[key]["content"] for key in ("identity", "voice")]
    if scene and profiles["scene"]["enabled"]:
        parts.append(profiles["scene"]["content"])
    return "\n\n".join(part for part in parts if part)


async def load_runtime_profiles():
    """Return editable runtime profiles separately so mandatory sections stay identifiable."""
    async with get_db() as db:
        async with db.execute(
            "SELECT key, content, enabled FROM prompt_profiles WHERE key IN ('identity','voice','scene')"
        ) as cur:
            rows = {row["key"]: dict(row) for row in await cur.fetchall()}
    return {
        key: {
            "content": rows.get(key, {}).get("content", ""),
            "enabled": bool(rows.get(key, {}).get("enabled", False)),
        }
        for key in ("identity", "voice", "scene")
    }
