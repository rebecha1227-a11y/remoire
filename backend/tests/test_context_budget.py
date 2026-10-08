import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app import database
from app.llm import ModelConfig
from app.services import chat_service
from app.services import context_budget_service
from app.services import model_settings_service


class ContextBudgetTests(unittest.IsolatedAsyncioTestCase):
    def test_core_folding_preserves_different_facts(self):
        text = "这是一条很长而且有很多共同措辞的核心记录，生日是在五月一日。"
        memories = [{"content": text}, {"content": text.replace("五月", "六月")}, {"content": text}]
        self.assertEqual(chat_service._deduplicate_core_memories(memories), memories[:2])

    async def test_switch_unknown_model_does_not_inherit_large_window(self):
        common = {"nickname": "test", "api_key": "test", "base_url": "https://example.com/v1"}
        known = await model_settings_service.create_preset({**common, "model_name": "claude-opus-4-6"})
        unknown = await model_settings_service.create_preset({**common, "model_name": "unknown-test"})
        await model_settings_service.update_slot("daily", preset_id=known["id"])
        updated = await model_settings_service.update_slot("daily", preset_id=unknown["id"])
        self.assertEqual(updated["context_window"], 32768)
        self.assertEqual(updated["output_budget"], 4096)

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stack = ExitStack()
        self.stack.enter_context(
            patch.object(database, "DATABASE_PATH", str(Path(self.tmp.name) / "context.db"))
        )
        await database.init_db()

    async def asyncTearDown(self):
        self.stack.close()
        self.tmp.cleanup()

    def test_mandatory_profiles_and_latest_input_are_never_trimmed(self):
        identity = "IDENTITY-MARKER\n" + "身份关系" * 300
        voice = "VOICE-MARKER\n" + "表达语气" * 300
        latest = "LATEST-EXACT-INPUT\n" + "这是本轮最新输入" * 20
        history = []
        start = datetime(2026, 10, 1)
        for index in range(30):
            history.append({
                "id": f"m-{index}",
                "role": "assistant" if index % 2 else "user",
                "content": (f"旧消息{index} " + "旧内容" * 100),
                "created_at": (start + timedelta(minutes=index)).isoformat(),
            })
        history[-1] = {
            "id": "latest",
            "role": "user",
            "content": latest,
            "created_at": (start + timedelta(minutes=31)).isoformat(),
        }
        collected = {
            "mandatory_parts": [identity, voice, "固定系统规则"],
            "dynamic_parts": ["当前时间", "天气" * 200],
            "core_memories": [{"content": f"核心记忆{index}"} for index in range(8)],
            "recalled_memories": [{"content": f"召回{index} " + "细节" * 100} for index in range(10)],
        }
        messages, selected, diagnostics = chat_service._build_budgeted_chat_context(
            collected,
            history,
            {
                "summary": "过去摘要" * 80,
                "through_message_id": "older-message",
            },
            [],
            {"context_window": 8192, "output_budget": 1024},
            user_message=latest,
        )
        self.assertIn("IDENTITY-MARKER", messages[0]["content"])
        self.assertIn("VOICE-MARKER", messages[0]["content"])
        for index in range(8):
            self.assertIn(f"核心记忆{index}", messages[0]["content"])
        self.assertEqual(messages[-1]["content"], latest)
        self.assertEqual(selected[-1]["id"], "latest")
        self.assertLessEqual(diagnostics["estimated_input_tokens"], diagnostics["input_budget"])
        self.assertEqual(diagnostics["core_memories_mandatory"], 8)
        self.assertTrue(diagnostics["history_omitted"] > 0)

    def test_oversized_mandatory_layer_returns_explicit_error(self):
        collected = {
            "mandatory_parts": ["身份与表达" * 4000],
            "dynamic_parts": [],
            "core_memories": [],
            "recalled_memories": [],
        }
        history = [{
            "id": "latest",
            "role": "user",
            "content": "请回应我",
            "created_at": "2026-10-08T00:00:00",
        }]
        with self.assertRaises(context_budget_service.ContextBudgetError) as caught:
            chat_service._build_budgeted_chat_context(
                collected,
                history,
                None,
                [],
                {"context_window": 8192, "output_budget": 1024},
                user_message="请回应我",
            )
        self.assertIn("没有截断", str(caught.exception))
        self.assertIn("mandatory_tokens", caught.exception.details)

    async def test_rolling_summary_advances_contiguous_coverage_without_duplicates(self):
        conversation_id = "summary-test"
        async with database.get_db() as db:
            await db.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conversation_id, "test", "2026-10-01", "2026-10-01"),
            )
            for index in range(1, 36):
                await db.execute(
                    """INSERT INTO messages
                       (id, conversation_id, role, content, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (f"m-{index}", conversation_id, "user" if index % 2 else "assistant",
                     f"原始消息 {index}", f"2026-10-01T00:{index:02d}:00"),
                )
            await db.commit()

        llm = AsyncMock(side_effect=["第一版连续摘要", "第二版连续摘要"])
        slot = {
            "context_window": 32768,
            "output_budget": 4096,
        }
        with patch.object(
            model_settings_service,
            "get_model_config_for_slot",
            AsyncMock(return_value=(ModelConfig("https://invalid", "fake", "test"), slot)),
        ), patch.object(context_budget_service, "call_llm", llm):
            self.assertTrue(await context_budget_service.maybe_compact_conversation(conversation_id))
            first = await context_budget_service.get_conversation_summary(conversation_id)
            self.assertEqual(first["through_message_id"], "m-23")
            self.assertEqual(first["source_message_count"], 23)

            async with database.get_db() as db:
                for index in range(36, 56):
                    await db.execute(
                        """INSERT INTO messages
                           (id, conversation_id, role, content, created_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (f"m-{index}", conversation_id, "user" if index % 2 else "assistant",
                         f"原始消息 {index}", f"2026-10-02T00:{index - 36:02d}:00"),
                    )
                await db.commit()

            self.assertTrue(await context_budget_service.maybe_compact_conversation(conversation_id))
            second = await context_budget_service.get_conversation_summary(conversation_id)

        self.assertEqual(second["through_message_id"], "m-43")
        self.assertEqual(second["source_message_count"], 43)
        self.assertEqual(second["version"], 2)
        second_source = llm.await_args_list[1].args[1][1]["content"]
        self.assertIn("【此前摘要】\n第一版连续摘要", second_source)
        self.assertIn("[24 |", second_source)
        self.assertNotIn("[23 |", second_source)
        self.assertIn("[43 |", second_source)
        self.assertNotIn("[44 |", second_source)

    async def test_slot_budgets_are_persisted_per_model_role(self):
        updated = await model_settings_service.update_slot(
            "daily",
            context_window=65536,
            output_budget=8192,
        )
        self.assertEqual(updated["context_window"], 65536)
        self.assertEqual(updated["output_budget"], 8192)
        slots = {item["slot"]: item for item in await model_settings_service.list_slots()}
        self.assertEqual(slots["daily"]["context_window"], 65536)
        self.assertEqual(slots["daily"]["output_budget"], 8192)

    async def test_claude_opus_46_slot_uses_automatic_model_capabilities(self):
        preset = await model_settings_service.create_preset({
            "nickname": "Claude",
            "provider": "openai-compatible",
            "api_key": "test-key",
            "base_url": "https://gateway.example/v1",
            "model_name": "「按量」claude-opus-4-6-渠道2",
        })
        updated = await model_settings_service.update_slot("daily", preset_id=preset["id"])
        self.assertEqual(updated["context_window"], 1_000_000)
        self.assertEqual(updated["output_budget"], 128_000)
        self.assertTrue(updated["capabilities"]["prompt_caching"])


if __name__ == "__main__":
    unittest.main()
