import aiosqlite
import os
from app.config import DATABASE_PATH
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=5000")
        db.row_factory = aiosqlite.Row
        yield db

async def init_db():
    async with get_db() as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                display_name TEXT,
                config_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS channel_bindings (
                id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL REFERENCES channels(id),
                external_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                channel_id TEXT REFERENCES channels(id),
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                thinking TEXT,
                channel TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_candidates (
                id TEXT PRIMARY KEY,
                conversation_id TEXT REFERENCES conversations(id),
                message_id TEXT REFERENCES messages(id),
                content TEXT NOT NULL,
                tags_json TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tags_json TEXT,
                embedding BLOB,
                source_candidate_id TEXT REFERENCES memory_candidates(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                conversation_id TEXT REFERENCES conversations(id),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                kept INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                read_at TEXT
            );

            CREATE TABLE IF NOT EXISTS diary_entries (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT 'connie',
                source TEXT,
                locked INTEGER NOT NULL DEFAULT 0,
                pin TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS diary_interactions (
                id TEXT PRIMARY KEY,
                diary_id TEXT NOT NULL REFERENCES diary_entries(id) ON DELETE CASCADE,
                actor TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT,
                status TEXT NOT NULL DEFAULT 'visible',
                seen_by_connie INTEGER NOT NULL DEFAULT 0,
                seen_by_jinger INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_settings (
                slot TEXT PRIMARY KEY,
                api_base TEXT NOT NULL,
                api_key TEXT NOT NULL,
                model_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS proactive_message_settings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                min_interval_hours INTEGER NOT NULL DEFAULT 4,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id TEXT PRIMARY KEY,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                user_agent TEXT,
                created_at TEXT NOT NULL,
                last_used_at TEXT
            );

            CREATE TABLE IF NOT EXISTS device_snapshots (
                id TEXT PRIMARY KEY,
                latitude REAL,
                longitude REAL,
                city TEXT,
                district TEXT,
                weather TEXT,
                battery_level INTEGER,
                battery_charging INTEGER,
                steps INTEGER,
                raw_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_usage_events (
                id TEXT PRIMARY KEY,
                app_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usage_logs (
                id TEXT PRIMARY KEY,
                slot TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_memory_candidates_status
                ON memory_candidates(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_memories_created
                ON memories(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_reminders_status
                ON reminders(status, remind_at);
            CREATE INDEX IF NOT EXISTS idx_diary_entries_author_created
                ON diary_entries(author, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_diary_interactions_diary_created
                ON diary_interactions(diary_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_diary_interactions_created
                ON diary_interactions(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_device_snapshots_created
                ON device_snapshots(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_app_usage_app_created
                ON app_usage_events(app_name, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_notes_unread
                ON notes(is_read) WHERE is_read = 0;
        """)
        # 兼容已有数据库：补加新列
        for col_sql in [
            "ALTER TABLE notes ADD COLUMN kept INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE notes ADD COLUMN read_at TEXT",
            "ALTER TABLE diary_entries ADD COLUMN locked INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE diary_entries ADD COLUMN pin TEXT",
            "ALTER TABLE diary_interactions ADD COLUMN seen_by_connie INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE diary_interactions ADD COLUMN seen_by_jinger INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                await db.execute(col_sql)
            except Exception:
                pass
        await db.commit()
