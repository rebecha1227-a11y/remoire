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
                image TEXT,
                channel TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_candidates (
                id TEXT PRIMARY KEY,
                conversation_id TEXT REFERENCES conversations(id),
                message_id TEXT REFERENCES messages(id),
                content TEXT NOT NULL,
                tags_json TEXT,
                proposed_memory_type TEXT,
                proposed_layer TEXT DEFAULT 'long',
                confidence REAL DEFAULT 0.5,
                proposed_event_date TEXT,
                proposed_valence REAL DEFAULT 0.5,
                proposed_arousal REAL DEFAULT 0.0,
                proposed_unresolved INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tags_json TEXT,
                layer TEXT NOT NULL DEFAULT 'long',
                memory_type TEXT NOT NULL DEFAULT 'fact',
                event_date TEXT,
                event_time TEXT,
                timezone TEXT DEFAULT 'Asia/Shanghai',
                expires_at TEXT,
                weight REAL NOT NULL DEFAULT 1.0,
                decay_rate REAL NOT NULL DEFAULT 0.05,
                valence REAL NOT NULL DEFAULT 0.0,
                arousal REAL NOT NULL DEFAULT 0.0,
                pinned INTEGER NOT NULL DEFAULT 0,
                unresolved INTEGER NOT NULL DEFAULT 0,
                last_triggered_at TEXT,
                trigger_count INTEGER NOT NULL DEFAULT 0,
                embedding BLOB,
                source_candidate_id TEXT REFERENCES memory_candidates(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                urgent INTEGER NOT NULL DEFAULT 0,
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
                meta_json TEXT,
                locked INTEGER NOT NULL DEFAULT 0,
                pin TEXT,
                pin_hash TEXT,
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

            CREATE TABLE IF NOT EXISTS model_presets (
                id TEXT PRIMARY KEY,
                nickname TEXT NOT NULL,
                provider TEXT,
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                model_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_slots (
                slot TEXT PRIMARY KEY,
                preset_id TEXT REFERENCES model_presets(id) ON DELETE SET NULL,
                extended_thinking INTEGER NOT NULL DEFAULT 0,
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

            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                csrf_hash TEXT NOT NULL,
                username TEXT NOT NULL,
                user_agent TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_digest_runs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                proposed_json TEXT NOT NULL DEFAULT '[]',
                applied_json TEXT NOT NULL DEFAULT '[]',
                skipped_json TEXT NOT NULL DEFAULT '[]',
                deleted_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS memory_recall_logs (
                id TEXT PRIMARY KEY,
                query_hash TEXT NOT NULL,
                keyword_hits INTEGER NOT NULL DEFAULT 0,
                semantic_hits INTEGER NOT NULL DEFAULT 0,
                result_count INTEGER NOT NULL DEFAULT 0,
                latency_ms REAL NOT NULL DEFAULT 0,
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
            CREATE INDEX IF NOT EXISTS idx_model_presets_created
                ON model_presets(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_device_snapshots_created
                ON device_snapshots(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_app_usage_app_created
                ON app_usage_events(app_name, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires
                ON auth_sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_memory_digest_runs_created
                ON memory_digest_runs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_memory_recall_logs_created
                ON memory_recall_logs(created_at DESC);
            CREATE TABLE IF NOT EXISTS weather_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temp TEXT,
                feels_like TEXT,
                text TEXT,
                humidity TEXT,
                wind_dir TEXT,
                wind_scale TEXT,
                precip TEXT,
                icon TEXT,
                obs_time TEXT,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS breath_states (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_links (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                target_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                link_type TEXT NOT NULL DEFAULT 'relates_to',
                weight REAL NOT NULL DEFAULT 0.5,
                description TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS nudge_sessions (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                round INTEGER NOT NULL DEFAULT 1,
                max_rounds INTEGER NOT NULL DEFAULT 3,
                messages_sent INTEGER NOT NULL DEFAULT 0,
                max_messages INTEGER NOT NULL DEFAULT 8,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_sent_at TEXT,
                next_follow_up_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_nudge_sessions_status
                ON nudge_sessions(status, next_follow_up_at);

            CREATE INDEX IF NOT EXISTS idx_breath_states_created
                ON breath_states(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_notes_unread
                ON notes(is_read) WHERE is_read = 0;
            CREATE INDEX IF NOT EXISTS idx_memory_links_source
                ON memory_links(source_id);
            CREATE INDEX IF NOT EXISTS idx_memory_links_target
                ON memory_links(target_id);

            CREATE TABLE IF NOT EXISTS autonomous_logs (
                id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL DEFAULT 'none',
                thinking TEXT DEFAULT '',
                action_summary TEXT DEFAULT '',
                detail_json TEXT DEFAULT '{}',
                mode TEXT NOT NULL DEFAULT 'light',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_autonomous_logs_created
                ON autonomous_logs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_autonomous_logs_date
                ON autonomous_logs(created_at);

            CREATE TABLE IF NOT EXISTS browsed_content (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL DEFAULT 'web',
                title TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                shared INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_browsed_content_created
                ON browsed_content(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_browsed_content_unshared
                ON browsed_content(shared) WHERE shared = 0;
        """)
        # 兼容已有数据库：补加新列
        for col_sql in [
            "ALTER TABLE notes ADD COLUMN kept INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE notes ADD COLUMN read_at TEXT",
            "ALTER TABLE diary_entries ADD COLUMN meta_json TEXT",
            "ALTER TABLE diary_entries ADD COLUMN locked INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE diary_entries ADD COLUMN pin TEXT",
            "ALTER TABLE diary_entries ADD COLUMN pin_hash TEXT",
            "ALTER TABLE diary_interactions ADD COLUMN seen_by_connie INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE diary_interactions ADD COLUMN seen_by_jinger INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE messages ADD COLUMN image TEXT",
            "ALTER TABLE memories ADD COLUMN layer TEXT NOT NULL DEFAULT 'long'",
            "ALTER TABLE memories ADD COLUMN memory_type TEXT NOT NULL DEFAULT 'fact'",
            "ALTER TABLE memories ADD COLUMN event_date TEXT",
            "ALTER TABLE memories ADD COLUMN event_time TEXT",
            "ALTER TABLE memories ADD COLUMN timezone TEXT DEFAULT 'Asia/Shanghai'",
            "ALTER TABLE memories ADD COLUMN expires_at TEXT",
            "ALTER TABLE memories ADD COLUMN weight REAL NOT NULL DEFAULT 1.0",
            "ALTER TABLE memories ADD COLUMN decay_rate REAL NOT NULL DEFAULT 0.05",
            "ALTER TABLE memories ADD COLUMN valence REAL NOT NULL DEFAULT 0.0",
            "ALTER TABLE memories ADD COLUMN arousal REAL NOT NULL DEFAULT 0.0",
            "ALTER TABLE memories ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE memories ADD COLUMN unresolved INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE memories ADD COLUMN last_triggered_at TEXT",
            "ALTER TABLE memories ADD COLUMN trigger_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE memory_candidates ADD COLUMN proposed_memory_type TEXT",
            "ALTER TABLE memory_candidates ADD COLUMN proposed_layer TEXT DEFAULT 'long'",
            "ALTER TABLE memory_candidates ADD COLUMN confidence REAL DEFAULT 0.5",
            "ALTER TABLE memory_candidates ADD COLUMN proposed_event_date TEXT",
            "ALTER TABLE memory_candidates ADD COLUMN proposed_valence REAL DEFAULT 0.5",
            "ALTER TABLE memory_candidates ADD COLUMN proposed_arousal REAL DEFAULT 0.0",
            "ALTER TABLE memory_candidates ADD COLUMN proposed_unresolved INTEGER DEFAULT 0",
            "ALTER TABLE push_subscriptions ADD COLUMN display_name TEXT DEFAULT 'Connie'",
            "ALTER TABLE reminders ADD COLUMN urgent INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE proactive_message_settings ADD COLUMN start_hour INTEGER NOT NULL DEFAULT 9",
            "ALTER TABLE proactive_message_settings ADD COLUMN end_hour INTEGER NOT NULL DEFAULT 23",
            "ALTER TABLE proactive_message_settings ADD COLUMN allow_night INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE proactive_message_settings ADD COLUMN max_daily INTEGER NOT NULL DEFAULT 5",
            "ALTER TABLE proactive_message_settings ADD COLUMN cooldown_minutes INTEGER NOT NULL DEFAULT 60",
            "ALTER TABLE proactive_message_settings ADD COLUMN max_burst INTEGER NOT NULL DEFAULT 8",
            "ALTER TABLE proactive_message_settings ADD COLUMN max_rounds INTEGER NOT NULL DEFAULT 3",
            "ALTER TABLE proactive_message_settings ADD COLUMN round_interval_minutes INTEGER NOT NULL DEFAULT 30",
            "ALTER TABLE proactive_message_settings ADD COLUMN end_on_reply INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE proactive_message_settings ADD COLUMN types_json TEXT DEFAULT '{\"care\":true,\"reminder\":true,\"followup\":true,\"special\":true}'",
        ]:
            try:
                await db.execute(col_sql)
            except Exception:
                pass
        # Upgrade legacy recoverable PINs before the application starts serving.
        from app.services.diary_pin import hash_pin
        async with db.execute(
            "SELECT id, pin FROM diary_entries WHERE pin IS NOT NULL AND pin <> '' AND pin_hash IS NULL"
        ) as cursor:
            legacy_pins = await cursor.fetchall()
        for row in legacy_pins:
            await db.execute(
                "UPDATE diary_entries SET pin_hash = ?, pin = NULL WHERE id = ?",
                (hash_pin(row["pin"]), row["id"]),
            )
        await db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_diary_entries_auto_day
                ON diary_entries(author, source, json_extract(meta_json, '$.date_key'))
                WHERE author = 'connie' AND source = 'auto' AND json_extract(meta_json, '$.date_key') IS NOT NULL
        """)
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_memories_layer ON memories(layer, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_memories_event_date ON memories(event_date) WHERE event_date IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_memories_weight ON memories(weight DESC)",
            "CREATE INDEX IF NOT EXISTS idx_memories_layer_weight ON memories(layer, weight DESC)",
        ]:
            try:
                await db.execute(idx_sql)
            except Exception:
                pass
        await db.execute("UPDATE memories SET layer = 'core' WHERE pinned = 1 AND layer = 'long'")
        async with db.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            ("2026-08-12-unresolved-invariant",),
        ) as cursor:
            unresolved_migrated = await cursor.fetchone()
        if not unresolved_migrated:
            # Older writers stored the type and active flag independently. No resolve()
            # operation existed, so false flags on unresolved types were migration defaults,
            # not user decisions. Normalize once; future resolved items stay resolved.
            await db.execute(
                "UPDATE memories SET memory_type = 'unresolved' WHERE unresolved = 1 AND memory_type <> 'unresolved'"
            )
            await db.execute(
                "UPDATE memories SET unresolved = 1 WHERE memory_type = 'unresolved' AND unresolved = 0"
            )
            await db.execute(
                """UPDATE memory_candidates
                   SET proposed_unresolved = 1
                   WHERE proposed_memory_type = 'unresolved'"""
            )
            await db.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                ("2026-08-12-unresolved-invariant",),
            )
        async with db.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            ("2026-08-12-decay-rate-invariant",),
        ) as cursor:
            decay_migrated = await cursor.fetchone()
        if not decay_migrated:
            await db.execute("UPDATE memories SET decay_rate = 0.0 WHERE layer IN ('core', 'consciousness')")
            await db.execute("UPDATE memories SET decay_rate = 0.995 WHERE layer = 'long'")
            await db.execute("UPDATE memories SET decay_rate = 0.95 WHERE layer = 'short'")
            await db.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                ("2026-08-12-decay-rate-invariant",),
            )
        async with db.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            ("2026-08-12-memory-link-integrity",),
        ) as cursor:
            links_migrated = await cursor.fetchone()
        if not links_migrated:
            await db.execute(
                """DELETE FROM memory_links
                   WHERE source_id NOT IN (SELECT id FROM memories)
                      OR target_id NOT IN (SELECT id FROM memories)
                      OR source_id = target_id"""
            )
            await db.execute(
                """DELETE FROM memory_links WHERE rowid NOT IN (
                       SELECT MIN(rowid) FROM memory_links
                       GROUP BY source_id, target_id, link_type
                   )"""
            )
            await db.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_links_unique
                   ON memory_links(source_id, target_id, link_type)"""
            )
            await db.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                ("2026-08-12-memory-link-integrity",),
            )
        await db.commit()
