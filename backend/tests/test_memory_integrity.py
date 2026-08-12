import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app import database
from app.database import get_db, init_db
from app.services import memory_service
from app.scheduler import jobs


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

    async def test_recall_has_no_random_or_recent_fallback(self):
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, created_at, updated_at)
                   VALUES ('unrelated', '完全无关的一段内容', '[]', 'long', 'fact', ?, ?)""",
                (now, now),
            )
            await db.commit()
        with patch.object(memory_service, "_generate_embedding", AsyncMock(return_value=None)):
            self.assertEqual(await memory_service.recall("蒙特利尔留学", limit=5), [])

    async def test_recall_uses_calibrated_semantic_floor(self):
        now = datetime.utcnow().isoformat()
        high = json.dumps([0.8, 0.6]).encode()
        low = json.dumps([0.69, (1 - 0.69**2) ** 0.5]).encode()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, embedding, created_at, updated_at)
                   VALUES ('high', '高相关语义', '[]', 'long', 'fact', ?, ?, ?),
                          ('low', '背景相似语义', '[]', 'long', 'fact', ?, ?, ?)""",
                (high, now, now, low, now, now),
            )
            await db.commit()
        with patch.object(memory_service, "_generate_embedding", AsyncMock(return_value=[1.0, 0.0])):
            results = await memory_service.recall("查询文本", limit=5)
        self.assertEqual([item["id"] for item in results], ["high"])

    async def test_recall_trigger_is_cooled_down_and_does_not_rewrite_updated_at(self):
        original = "2026-01-01T00:00:00"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, created_at, updated_at)
                   VALUES ('match', '静儿喜欢热拿铁', '[]', 'long', 'fact', ?, ?)""",
                (original, original),
            )
            await db.commit()
        with patch.object(memory_service, "_generate_embedding", AsyncMock(return_value=None)):
            await memory_service.recall("热拿铁")
            await memory_service.recall("热拿铁")
        async with get_db() as db:
            row = await (await db.execute(
                "SELECT trigger_count, updated_at FROM memories WHERE id = 'match'"
            )).fetchone()
        self.assertEqual(row["trigger_count"], 1)
        self.assertEqual(row["updated_at"], original)

    async def test_write_time_association_does_not_count_as_recall(self):
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, embedding, created_at, updated_at)
                   VALUES ('old', '静儿喜欢热拿铁', '["咖啡"]', 'long', 'fact', ?, ?, ?)""",
                (json.dumps([1.0, 0.0]).encode(), now, now),
            )
            await db.commit()
        with patch.object(memory_service, "_generate_embedding", AsyncMock(return_value=[1.0, 0.0])):
            associated = await memory_service.find_associated("静儿爱喝热拿铁", ["咖啡"])
        self.assertEqual([item["id"] for item in associated], ["old"])
        async with get_db() as db:
            row = await (await db.execute(
                "SELECT trigger_count, last_triggered_at FROM memories WHERE id = 'old'"
            )).fetchone()
        self.assertEqual(row["trigger_count"], 0)
        self.assertIsNone(row["last_triggered_at"])

    def test_mmr_diversifies_near_duplicate_results(self):
        packed_a = json.dumps([1.0, 0.0]).encode()
        packed_c = json.dumps([0.0, 1.0]).encode()
        scored = [
            {"memory": {"id": "a", "content": "a", "embedding": packed_a}, "score": 0.90},
            {"memory": {"id": "b", "content": "a copy", "embedding": packed_a}, "score": 0.89},
            {"memory": {"id": "c", "content": "different", "embedding": packed_c}, "score": 0.82},
        ]
        selected = memory_service._diversify_results(scored, 2)
        self.assertEqual([item["memory"]["id"] for item in selected], ["a", "c"])

    async def test_related_memories_are_bidirectional_and_ranked(self):
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories (id, content, tags_json, layer, memory_type, created_at, updated_at)
                   VALUES ('center', '中心', '[]', 'long', 'fact', ?, ?),
                          ('left', '左侧', '[]', 'long', 'fact', ?, ?),
                          ('right', '右侧', '[]', 'long', 'fact', ?, ?)""",
                (now, now, now, now, now, now),
            )
            await db.execute(
                """INSERT INTO memory_links (id, source_id, target_id, link_type, weight, created_at)
                   VALUES ('a', 'left', 'center', 'relates_to', 0.7, ?),
                          ('b', 'center', 'right', 'relates_to', 0.9, ?)""",
                (now, now),
            )
            await db.commit()
        related = await memory_service.get_related_memories("center")
        self.assertEqual([item["id"] for item in related], ["right", "left"])

    async def test_decay_protects_active_and_conscious_memories(self):
        old = "2020-01-01T00:00:00"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memories
                   (id, content, tags_json, layer, memory_type, weight, unresolved, expires_at, created_at, updated_at)
                   VALUES ('active', '进行中', '[]', 'long', 'unresolved', 1, 1, NULL, ?, ?),
                          ('ordinary', '普通长期', '[]', 'long', 'fact', 1, 0, NULL, ?, ?),
                          ('expired', '过期短期', '[]', 'short', 'fact', 1, 0, ?, ?, ?),
                          ('mind', '内心记忆', '[]', 'consciousness', 'consciousness', 1, 0, ?, ?, ?)""",
                (old, old, old, old, old, old, old, old, old, old),
            )
            await db.commit()
        await jobs.decay_memories()
        self.assertEqual((await memory_service.get_memory("active"))["weight"], 1)
        self.assertAlmostEqual((await memory_service.get_memory("ordinary"))["weight"], 0.995)
        self.assertIsNone(await memory_service.get_memory("expired"))
        self.assertIsNotNone(await memory_service.get_memory("mind"))


if __name__ == "__main__":
    unittest.main()
