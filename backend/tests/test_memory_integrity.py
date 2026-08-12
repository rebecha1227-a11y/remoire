import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app import database
from app.database import get_db, init_db
from app.services import memory_service


class MemoryIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = str(Path(self.tempdir.name) / "memory.db")
        await init_db()

    async def asyncTearDown(self):
        self.tempdir.cleanup()

    async def test_create_normalizes_unresolved_type_and_flag(self):
        with patch.object(memory_service, "_is_duplicate", AsyncMock(return_value=False)), patch.object(
            memory_service, "_generate_embedding", AsyncMock(return_value=None)
        ), patch.object(memory_service, "find_associated", AsyncMock(return_value=[])):
            result = await memory_service.create_memory(
                "还有一件事没有完成", memory_type="unresolved"
            )
        stored = await memory_service.get_memory(result["memory"]["id"])
        self.assertEqual(stored["memory_type"], "unresolved")
        self.assertTrue(stored["unresolved"])

    async def test_resolve_preserves_history_and_is_not_reactivated(self):
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, unresolved, created_at, updated_at)
                   VALUES ('task', '完成测试', '[]', 'long', 'unresolved', 1, ?, ?)""",
                (now, now),
            )
            await db.commit()
        resolved = await memory_service.resolve_memory("task")
        self.assertFalse(resolved["unresolved"])
        self.assertEqual(resolved["memory_type"], "unresolved")

        await init_db()
        self.assertFalse((await memory_service.get_memory("task"))["unresolved"])

    async def test_one_time_migration_repairs_legacy_inconsistency(self):
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            await db.execute(
                "DELETE FROM schema_migrations WHERE version = '2026-08-12-unresolved-invariant'"
            )
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, unresolved, created_at, updated_at)
                   VALUES ('legacy-type', '旧待办', '[]', 'long', 'unresolved', 0, ?, ?),
                          ('legacy-flag', '旧进行中', '[]', 'long', 'event', 1, ?, ?)""",
                (now, now, now, now),
            )
            await db.commit()
        await init_db()
        by_type = await memory_service.get_memory("legacy-type")
        by_flag = await memory_service.get_memory("legacy-flag")
        self.assertTrue(by_type["unresolved"])
        self.assertEqual(by_flag["memory_type"], "unresolved")

    async def test_content_edit_never_keeps_stale_embedding(self):
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, embedding, created_at, updated_at)
                   VALUES ('editable', '旧内容', '[]', 'long', 'fact', ?, ?, ?)""",
                (json.dumps([1.0, 0.0]).encode(), now, now),
            )
            await db.commit()
        with patch.object(memory_service, "_generate_embedding", AsyncMock(return_value=None)):
            await memory_service.update_memory("editable", content="完全不同的新内容")
        async with get_db() as db:
            row = await (await db.execute(
                "SELECT content, embedding FROM memories WHERE id = 'editable'"
            )).fetchone()
        self.assertEqual(row["content"], "完全不同的新内容")
        self.assertIsNone(row["embedding"])

    async def test_candidate_accept_preserves_affect_and_active_state(self):
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memory_candidates
                   (id, content, tags_json, proposed_memory_type, proposed_layer,
                    confidence, proposed_valence, proposed_arousal, proposed_unresolved,
                    status, created_at)
                   VALUES ('candidate', '需要继续处理', '["待办"]', 'unresolved', 'long',
                           0.6, 0.2, 0.8, 1, 'pending', ?)""",
                (now,),
            )
            await db.commit()
        with patch.object(memory_service, "_is_duplicate", AsyncMock(return_value=False)), patch.object(
            memory_service, "_generate_embedding", AsyncMock(return_value=[0.1, 0.2])
        ), patch.object(memory_service, "find_associated", AsyncMock(return_value=[])):
            result = await memory_service.accept_candidate("candidate")
        stored = await memory_service.get_memory(result["memory"]["id"])
        self.assertEqual(stored["valence"], 0.2)
        self.assertEqual(stored["arousal"], 0.8)
        self.assertTrue(stored["unresolved"])

    async def test_digest_rejects_low_similarity_and_protected_deletes(self):
        rows = [
            {"id": "keep", "content": "静儿喜欢喝热拿铁", "layer": "long", "memory_type": "fact", "pinned": 0, "unresolved": 0, "weight": 1.0, "embedding": None},
            {"id": "different", "content": "静儿明天要去广州出差", "layer": "long", "memory_type": "event", "pinned": 0, "unresolved": 0, "weight": 1.0, "embedding": None},
            {"id": "protected", "content": "静儿喜欢喝热拿铁", "layer": "long", "memory_type": "fact", "pinned": 1, "unresolved": 0, "weight": 1.0, "embedding": None},
        ]
        accepted, skipped = memory_service._validate_digest_plan(rows, {
            "merge": [
                {"keep_id": "keep", "delete_ids": ["different"]},
                {"keep_id": "keep", "delete_ids": ["protected"]},
            ]
        })
        self.assertEqual(accepted, [])
        self.assertEqual(len(skipped), 2)

    async def test_digest_transaction_merges_metadata_and_rewires_links(self):
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, weight, arousal,
                    trigger_count, created_at, updated_at)
                   VALUES ('keep', '静儿喜欢热拿铁', '["咖啡"]', 'long', 'fact', 0.6, 0.2, 2, ?, ?),
                          ('duplicate', '静儿喜欢热拿铁', '["偏好"]', 'long', 'fact', 0.9, 0.7, 3, ?, ?),
                          ('related', '一起去过咖啡店', '[]', 'long', 'event', 1, 0, 0, ?, ?)""",
                (now, now, now, now, now, now),
            )
            await db.execute(
                """INSERT INTO memory_links
                   (id, source_id, target_id, link_type, weight, created_at)
                   VALUES ('link', 'duplicate', 'related', 'relates_to', 0.8, ?)""",
                (now,),
            )
            await db.commit()

        count = await memory_service._apply_digest_pairs([
            {"keep_id": "keep", "delete_id": "duplicate", "score": 1.0, "reason": "exact"}
        ])
        self.assertEqual(count, 1)
        self.assertIsNone(await memory_service.get_memory("duplicate"))
        kept = await memory_service.get_memory("keep")
        self.assertEqual(set(kept["tags"]), {"咖啡", "偏好"})
        self.assertEqual(kept["weight"], 0.9)
        self.assertEqual(kept["arousal"], 0.7)
        self.assertEqual(kept["trigger_count"], 5)
        async with get_db() as db:
            link = await (await db.execute(
                "SELECT source_id, target_id FROM memory_links"
            )).fetchone()
        self.assertEqual((link["source_id"], link["target_id"]), ("keep", "related"))


if __name__ == "__main__":
    unittest.main()
