import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, database
from app.auth import verify_token
from app.database import init_db
from app.routers import imessage as imessage_router
from app.routers import settings as settings_router
from app.services import imessage_interactions, chat_service, imessage_service, model_settings_service, nudge_service
from app.services.chat_service import _build_llm_history_with_time_gaps
from app.services.imessage_format import bubble_delay_ms, sanitize_bubbles


class ImessageBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_path = database.DATABASE_PATH
        database.DATABASE_PATH = str(Path(self.tempdir.name) / "imessage.db")
        imessage_service.reset_runtime_state()
        imessage_service._STATE["auto_fire"] = False
        await init_db()
        self.secret_key = Fernet.generate_key().decode("ascii")
        self.key_patch = patch.object(model_settings_service, "MODEL_SECRET_ENCRYPTION_KEYS", [self.secret_key])
        self.key_patch.start()
        self.llm = AsyncMock(return_value={"content": "在的\n\n刚看见", "tool_calls": None})
        self.extract = AsyncMock()
        self.reminders = AsyncMock(return_value=[])
        self.compact = AsyncMock(return_value=False)
        self.recall = AsyncMock(return_value=[])
        self.core = AsyncMock(return_value=[])
        self.patches = [
            patch.object(chat_service, "call_llm_with_tools", self.llm),
            patch("app.services.memory_service.extract_candidates", self.extract),
            patch("app.services.memory_service.recall", self.recall),
            patch("app.services.memory_service.get_core_memories", self.core),
            patch("app.services.reminder_service.extract_reminders", self.reminders),
            patch("app.services.context_budget_service.maybe_compact_conversation", self.compact),
        ]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        imessage_service.reset_runtime_state()
        for item in self.patches:
            item.stop()
        self.key_patch.stop()
        database.DATABASE_PATH = self.original_path
        self.tempdir.cleanup()

    async def _enable(self, phone="+8613800138000"):
        await imessage_service.save_account({
            "enabled": True,
            "project_id": "project-1",
            "project_secret": "photon-secret-value",
            "owner_phone": phone,
            "merge_wait_seconds": 4,
        })

    async def _drain_background(self):
        current = asyncio.current_task()
        pending = [task for task in asyncio.all_tasks() if task is not current and not task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def test_merge_timer_still_sends_a_reply(self):
        await self._enable()
        imessage_service._STATE["auto_fire"] = True
        async def elapse(_seconds):
            imessage_service._STATE["last_received"] = 0

        with patch.object(imessage_service.asyncio, "sleep", new=elapse):
            await imessage_service.accept_inbound(
                external_id="timer-1",
                sender="+8613800138000",
                text="倒计时到了",
                chat_guid="chat-timer",
            )
            await self._drain_background()
        actions = await imessage_service.pending_actions()
        self.assertTrue(any(item["kind"] == "send" and item["body"] == "在的" for item in actions))

    async def test_owner_message_uses_chat_and_queues_human_rhythm(self):
        await self._enable()
        result = await imessage_service.accept_inbound(
            external_id="msg-1",
            sender="+86 138 0013 8000",
            text="我到了",
            chat_guid="chat-1",
        )
        self.assertTrue(result["queued"])
        await imessage_service.flush_pending()
        await self._drain_background()

        self.llm.assert_awaited()
        self.extract.assert_awaited()
        async with database.get_db() as db:
            async with db.execute("SELECT role, content, channel FROM messages ORDER BY created_at") as cur:
                rows = [dict(row) for row in await cur.fetchall()]
            async with db.execute("SELECT kind, body, delay_ms FROM imessage_outbox ORDER BY sequence") as cur:
                actions = [dict(row) for row in await cur.fetchall()]
        self.assertEqual([row["role"] for row in rows], ["user", "assistant"])
        self.assertEqual(rows[0]["channel"], "imessage")
        self.assertEqual(rows[0]["content"], "我到了")
        self.assertEqual([item["kind"] for item in actions], ["read", "typing_start", "send", "send", "typing_stop"])
        self.assertEqual(actions[2]["delay_ms"], 0)
        self.assertGreaterEqual(actions[3]["delay_ms"], 800)
        self.assertEqual(actions[2]["body"], "在的")
        self.assertNotIn("thinking", actions[2]["body"])

    async def test_stranger_is_dropped_without_model_or_memory(self):
        await self._enable()
        with self.assertLogs("remoire.imessage", level="INFO") as logs:
            result = await imessage_service.accept_inbound(
                external_id="stranger-1",
                sender="+19995550123",
                text="SECRET_BODY_991",
            )
        self.assertEqual(result["reason"], "rejected")
        self.llm.assert_not_awaited()
        self.extract.assert_not_awaited()
        joined = "\n".join(logs.output)
        self.assertNotIn("SECRET_BODY_991", joined)
        self.assertNotIn("+19995550123", joined)
        async with database.get_db() as db:
            async with db.execute("SELECT COUNT(*) AS n FROM messages") as cur:
                count = (await cur.fetchone())["n"]
        self.assertEqual(count, 0)

    async def test_duplicate_and_burst_become_one_turn(self):
        await self._enable()
        await imessage_service.accept_inbound(external_id="a", sender="+8613800138000", text="第一句", chat_guid="c")
        await imessage_service.accept_inbound(external_id="b", sender="+8613800138000", text="第二句", chat_guid="c")
        await imessage_service.accept_inbound(external_id="c", sender="+8613800138000", text="第三句", chat_guid="c")
        again = await imessage_service.accept_inbound(external_id="a", sender="+8613800138000", text="第一句", chat_guid="c")
        self.assertTrue(again["duplicate"])
        await imessage_service.flush_pending()
        await self._drain_background()
        self.assertEqual(self.llm.await_count, 1)
        sent = self.llm.await_args.args[1]
        user_bits = [item["content"] for item in sent if item.get("role") == "user"]
        self.assertTrue(any("第一句" in bit and "第二句" in bit and "第三句" in bit for bit in user_bits))
        async with database.get_db() as db:
            async with db.execute("SELECT COUNT(*) AS n FROM messages WHERE role = 'user'") as cur:
                users = (await cur.fetchone())["n"]
        self.assertEqual(users, 1)

    async def test_followups_during_generation_replace_obsolete_reply(self):
        await self._enable()
        started = asyncio.Event()
        release = asyncio.Event()
        calls = []

        async def slow_llm(*args, **_kwargs):
            calls.append(args[1])
            if len(calls) == 1:
                started.set()
                await release.wait()
                return {"content": "旧回答", "tool_calls": None}
            return {"content": "一起回答", "tool_calls": None}

        self.llm.side_effect = slow_llm
        await imessage_service.accept_inbound(external_id="first", sender="+8613800138000", text="先说", chat_guid="c")
        first = asyncio.create_task(imessage_service.flush_pending())
        await started.wait()
        await imessage_service.accept_inbound(external_id="second", sender="+8613800138000", text="再说", chat_guid="c")
        # A second consumer waiting for the lock must not steal pending input.
        second = asyncio.create_task(imessage_service.flush_pending())
        await asyncio.sleep(0)
        await imessage_service.accept_inbound(external_id="third", sender="+8613800138000", text="补充", chat_guid="c")
        release.set()
        await asyncio.gather(first, second)
        await self._drain_background()
        self.assertEqual(len(calls), 2)
        users = [m["content"] for m in calls[-1] if m["role"] == "user"]
        self.assertTrue(any("先说" in text for text in users))
        self.assertTrue(any("再说\n补充" in text for text in users))
        actions = await imessage_service.pending_actions()
        self.assertEqual([a["body"] for a in actions if a["kind"] == "send"], ["一起回答"])
        async with database.get_db() as db:
            async with db.execute("SELECT content FROM messages WHERE role = 'assistant'") as cur:
                self.assertEqual([r["content"] for r in await cur.fetchall()], ["一起回答"])
        self.extract.assert_awaited_once()

    async def test_superseded_tool_request_is_not_executed(self):
        await self._enable()
        calls = 0

        async def tool_reply(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                await imessage_service.accept_inbound(external_id="tool-b", sender="+8613800138000", text="先别做")
                return {"content": "", "tool_calls": [{"id": "t1", "function": {"name": "leave_note", "arguments": "{}"}}]}
            return {"content": "好的", "tool_calls": None}

        self.llm.side_effect = tool_reply
        with patch.object(chat_service, "execute_tool", new=AsyncMock()) as execute:
            await imessage_service.accept_inbound(external_id="tool-a", sender="+8613800138000", text="留纸条")
            await imessage_service.flush_pending()
            await self._drain_background()
            execute.assert_not_awaited()
        self.assertEqual(calls, 2)

    async def test_debounce_rechecks_last_arrival_without_cancelling_worker(self):
        await self._enable()
        imessage_service._STATE["auto_fire"] = True
        sleeps = []

        async def elapse(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 1:
                worker = imessage_service._STATE["task"]
                await imessage_service.accept_inbound(external_id="timer-b", sender="+8613800138000", text="第二句")
                self.assertIs(imessage_service._STATE["task"], worker)
                self.assertFalse(worker.cancelling())
            else:
                imessage_service._STATE["last_received"] = 0

        with patch.object(imessage_service.asyncio, "sleep", new=elapse):
            await imessage_service.accept_inbound(external_id="timer-a", sender="+8613800138000", text="第一句")
            await self._drain_background()
        self.assertEqual(len(sleeps), 2)
        self.assertEqual(self.llm.await_count, 1)
        users = [m["content"] for m in self.llm.await_args.args[1] if m["role"] == "user"]
        self.assertTrue(any("第一句\n第二句" in text for text in users))

    async def test_empty_event_does_not_supersede_generation(self):
        await self._enable()
        result = await imessage_service.accept_inbound(external_id="empty", sender="+8613800138000", text=" ")
        self.assertEqual(result.get("ignored"), "empty_text")
        self.assertTrue(await imessage_service._reply_is_current())
        self.assertEqual(imessage_service._STATE["last_received"], 0)

    async def test_quote_reaction_tools_and_ack_preserve_bubble_identity(self):
        await self._enable()
        self.llm.side_effect = [
            {"content": "", "tool_calls": [
                {"id": "t1", "function": {"name": "imessage_reply_to", "arguments": '{"target_id":"quoted-u"}'}},
                {"id": "t2", "function": {"name": "imessage_react", "arguments": '{"target_id":"quoted-u","reaction":"love"}'}},
            ]},
            {"content": "这一句的回答", "tool_calls": None},
        ]
        await imessage_service.accept_inbound(external_id="quoted-u", sender="+8613800138000", text="说的是那一句", chat_guid="c", reply_to="old-a", quote_text="旧引用内容")
        await imessage_service.flush_pending()
        await self._drain_background()
        actions = await imessage_service.pending_actions()
        reply = next(a for a in actions if a["kind"] == "reply")
        reaction = next(a for a in actions if a["kind"] == "reaction")
        self.assertEqual(reply["ref_id"], "quoted-u")
        self.assertEqual(reaction["body"], "❤️")
        await imessage_service.ack_action(reply["id"], True, external_id="sent-a")
        await imessage_service.ack_action(reply["id"], True, external_id="sent-a")
        await imessage_service.ack_action(reaction["id"], True, external_id="react-a")
        conv = await imessage_service._latest_conversation_id()
        history = await imessage_interactions.enrich_history(await chat_service.get_history(conv))
        user_bubble = history[0]["imessage_bubbles"][0]
        self.assertEqual(user_bubble["quote"], "旧引用内容")
        self.assertNotIn("reactions", user_bubble)
        async with database.get_db() as db:
            async with db.execute("SELECT emoji FROM imessage_reactions WHERE actor='assistant'") as cur:
                self.assertEqual((await cur.fetchone())["emoji"], "❤️")
        self.assertEqual(history[1]["imessage_bubbles"][0]["quote"], "说的是那一句")
        self.assertEqual(history[1]["imessage_bubbles"][0]["external_id"], "sent-a")
        self.assertEqual(len(history[1]["imessage_bubbles"]), 1)

    async def test_incoming_reaction_is_passive_and_seen_next_turn(self):
        await self._enable()
        await imessage_service.accept_inbound(external_id="r-u", sender="+8613800138000", text="在吗", chat_guid="c")
        await imessage_service.flush_pending()
        await self._drain_background()
        action = next(a for a in await imessage_service.pending_actions() if a["kind"] == "send")
        await imessage_service.ack_action(action["id"], True, external_id="r-a")
        self.llm.reset_mock()
        response = await imessage_service.accept_inbound(external_id="r-event", sender="+8613800138000", kind="reaction", text="", chat_guid="c", target_id="r-a", emoji="👍")
        self.assertTrue(response["reaction_saved"])
        self.llm.assert_not_awaited()
        self.assertEqual(imessage_service._STATE["items"], [])
        duplicate = await imessage_service.accept_inbound(external_id="r-event", sender="+8613800138000", kind="reaction", text="", chat_guid="c", target_id="r-a", emoji="👍")
        self.assertTrue(duplicate["duplicate"])
        await imessage_service.accept_inbound(external_id="r-next", sender="+8613800138000", text="继续", chat_guid="c")
        await imessage_service.flush_pending()
        await self._drain_background()
        context = str(self.llm.await_args.args[1])
        self.assertIn("👍", context)
        self.assertIn("r-a", context)

    async def test_reaction_only_needs_no_text_reply_or_extra_model_call(self):
        await self._enable()
        self.llm.return_value = {"content": "", "tool_calls": [{"id": "r", "function": {"name": "imessage_react", "arguments": '{"target_id":"only-u","reaction":"love","without_text":true}'}}]}
        await imessage_service.accept_inbound(external_id="only-u", sender="+8613800138000", text="贴个爱心就好", chat_guid="c")
        await imessage_service.flush_pending()
        await self._drain_background()
        actions = await imessage_service.pending_actions()
        self.assertEqual([a["kind"] for a in actions], ["read", "typing_start", "reaction", "typing_stop"])
        self.llm.assert_awaited_once()
        self.extract.assert_awaited_once()
        await imessage_service.ack_action(actions[2]["id"], False)
        async with database.get_db() as db:
            async with db.execute("SELECT count(*) AS n FROM imessage_reactions") as cur:
                self.assertEqual((await cur.fetchone())["n"], 0)

    async def test_reaction_to_legacy_message_keeps_target_snapshot(self):
        await self._enable()
        await imessage_service.accept_inbound(external_id="legacy-event", sender="+8613800138000", text="", kind="reaction", chat_guid="c", target_id="legacy-a", emoji="❤️", target_text="旧消息示例")
        await imessage_service.accept_inbound(external_id="legacy-next", sender="+8613800138000", text="继续", chat_guid="c")
        await imessage_service.flush_pending()
        await self._drain_background()
        self.assertIn("旧消息示例", str(self.llm.await_args.args[1]))
        self.llm.assert_awaited_once()

    async def test_superseded_turn_does_not_send_staged_reaction(self):
        await self._enable()
        calls = 0

        async def respond(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"content": "", "tool_calls": [{"id": "r", "function": {"name": "imessage_react", "arguments": '{"target_id":"draft-u","reaction":"love"}'}}]}
            if calls == 2:
                await imessage_service.accept_inbound(external_id="draft-next", sender="+8613800138000", text="先不贴", chat_guid="c")
                return {"content": "过期草稿", "tool_calls": None}
            return {"content": "好", "tool_calls": None}

        self.llm.side_effect = respond
        await imessage_service.accept_inbound(external_id="draft-u", sender="+8613800138000", text="hello", chat_guid="c")
        await imessage_service.flush_pending()
        await self._drain_background()
        actions = await imessage_service.pending_actions()
        self.assertFalse(any(a["kind"] == "reaction" for a in actions))
        self.assertEqual([a["body"] for a in actions if a["kind"] == "send"], ["好"])

    async def test_interaction_targets_are_scoped_and_migration_is_repeatable(self):
        await self._enable()
        await init_db()
        await imessage_service.accept_inbound(external_id="scope-u", sender="+8613800138000", text="hello", chat_guid="c")
        await imessage_service.flush_pending()
        await self._drain_background()
        conv = await imessage_service._latest_conversation_id()
        turn = await imessage_interactions.context_for_turn(conv, "other-chat", [])
        self.assertFalse(turn["targets"])
        result = await imessage_interactions.handle_tool("imessage_react", {"target_id": "scope-u", "reaction": "love"}, turn)
        self.assertIn("未执行", result)
        stranger = await imessage_service.accept_inbound(external_id="stranger-r", sender="+19995550123", text="", kind="reaction", chat_guid="c", target_id="scope-u", emoji="❤️")
        self.assertEqual(stranger["reason"], "rejected")

    async def test_markdown_and_tool_banner_are_removed_before_send(self):
        self.llm.return_value = {"content": "**你好**\n\n# 标题\n\n正在查记忆", "tool_calls": None}
        await self._enable()
        await imessage_service.accept_inbound(external_id="md", sender="+8613800138000", text="在吗", chat_guid="c")
        await imessage_service.flush_pending()
        await self._drain_background()
        async with database.get_db() as db:
            async with db.execute("SELECT body FROM imessage_outbox WHERE kind = 'send' ORDER BY sequence") as cur:
                bodies = [row["body"] for row in await cur.fetchall()]
        self.assertEqual(bodies, ["你好", "标题"])
        self.assertFalse(any("**" in body or "正在查记忆" in body or "#" in body for body in bodies))

    async def test_typing_failure_does_not_cancel_the_reply(self):
        await self._enable()
        await imessage_service.accept_inbound(external_id="ty", sender="+8613800138000", text="嗯", chat_guid="c")
        await imessage_service.flush_pending()
        actions = await imessage_service.pending_actions()
        typing = next(item for item in actions if item["kind"] == "typing_start")
        await imessage_service.ack_action(typing["id"], False)
        remaining = await imessage_service.pending_actions()
        self.assertTrue(any(item["kind"] == "send" for item in remaining))

    async def test_generation_failure_stays_off_imessage_unless_phrase_enabled(self):
        self.llm.side_effect = RuntimeError("HTTP 503 sk-secret")
        await self._enable()
        await imessage_service.accept_inbound(external_id="bad", sender="+8613800138000", text="PRIVATE_TEXT", chat_guid="c")
        with self.assertLogs("remoire.imessage", level="INFO") as logs:
            await imessage_service.flush_pending()
        joined = "\n".join(logs.output)
        self.assertNotIn("PRIVATE_TEXT", joined)
        self.assertNotIn("sk-secret", joined)
        self.assertNotIn("503", joined)
        actions = await imessage_service.pending_actions()
        self.assertFalse(any(item["kind"] == "send" for item in actions))
        account = await imessage_service.get_account()
        self.assertIn("没有生成", account["status_detail"])
        async with database.get_db() as db:
            async with db.execute("SELECT role, content FROM messages WHERE role = 'system'") as cur:
                system_rows = await cur.fetchall()
        self.assertTrue(system_rows)
        self.assertNotIn("503", system_rows[0]["content"])

        await imessage_service.save_account({"failure_phrase_enabled": True})
        self.llm.side_effect = RuntimeError("HTTP 503")
        await imessage_service.accept_inbound(external_id="bad-2", sender="+8613800138000", text="还在", chat_guid="c")
        await imessage_service.flush_pending()
        actions = await imessage_service.pending_actions()
        sends = [item for item in actions if item["kind"] == "send"]
        self.assertEqual([item["body"] for item in sends], ["我这边信号有点卡，等我一下"])

    async def test_secret_is_encrypted_and_hidden_from_settings(self):
        await self._enable()
        async with database.get_db() as db:
            async with db.execute("SELECT project_secret FROM imessage_accounts WHERE id = 1") as cur:
                stored = (await cur.fetchone())["project_secret"]
        self.assertTrue(stored.startswith("fernet:v1:"))
        self.assertNotIn("photon-secret-value", stored)
        public = imessage_service.public_account(await imessage_service.get_account())
        self.assertNotIn("project_secret", public)
        self.assertTrue(public["secret_saved"])
        await imessage_service.save_account({"merge_wait_seconds": 6})
        async with database.get_db() as db:
            async with db.execute("SELECT project_secret FROM imessage_accounts WHERE id = 1") as cur:
                kept = (await cur.fetchone())["project_secret"]
        self.assertTrue(kept.startswith("fernet:v1:"))
        self.assertNotIn("photon-secret-value", kept)
        runtime = await imessage_service.get_account(include_secret=True)
        self.assertEqual(runtime["project_secret"], "photon-secret-value")

    async def test_history_marks_the_door(self):
        rendered = _build_llm_history_with_time_gaps([
            {"role": "user", "content": "短信里说的", "channel": "imessage"},
            {"role": "user", "content": "网页里说的", "channel": None},
        ])
        self.assertEqual(rendered[0]["content"], "短信里说的")
        self.assertEqual(rendered[1]["content"], "网页里说的")

    async def test_history_strips_legacy_channel_prefix(self):
        rendered = _build_llm_history_with_time_gaps([
            {"role": "user", "content": "【来自 Remoire】旧记录", "channel": "remoire"},
        ])
        self.assertEqual(rendered[0]["content"], "旧记录")

    async def test_proactive_channel_and_wechat_rejection(self):
        pushed = AsyncMock()
        with patch("app.services.push_service.send_push", pushed):
            conversation_id = await chat_service.get_or_create_conversation(None)
            count = await nudge_service.send_nudge(conversation_id, "网页上的一句")
            self.assertEqual(count, 1)
            pushed.assert_awaited()

            await self._enable()
            async with database.get_db() as db:
                await db.execute(
                    "INSERT OR IGNORE INTO proactive_message_settings (id, updated_at) VALUES (1, ?)",
                    ("2026-10-09T00:00:00",),
                )
                await db.execute("UPDATE proactive_message_settings SET delivery_channel = 'imessage' WHERE id = 1")
                await db.commit()
            pushed.reset_mock()
            await nudge_service.send_nudge(conversation_id, "想你了")
            pushed.assert_awaited()
            account = await imessage_service.get_account()
            self.assertIn("网页通知", account["status_detail"])

            await imessage_service.set_status("connected", "", chat_guid="chat-9")
            pushed.reset_mock()
            await nudge_service.send_nudge(conversation_id, "这条走短信\n\n**第二句**")
            pushed.assert_not_awaited()
            actions = await imessage_service.pending_actions()
            bodies = [item["body"] for item in actions if item["kind"] == "send"]
            self.assertEqual(bodies, ["这条走短信", "第二句"])

    def test_delay_and_sanitize_helpers(self):
        self.assertEqual(bubble_delay_ms("你好呀", 45, first=True), 0)
        self.assertGreaterEqual(bubble_delay_ms("你好呀", 45, first=False, roll=0), 800)
        self.assertLessEqual(bubble_delay_ms("字" * 500, 100, first=False, roll=1), 6000)
        self.assertEqual(sanitize_bubbles("[链接](https://example.com)\n\n`代码`"), ["链接", "代码"])


class ImessageRouteTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = str(Path(self.tempdir.name) / "imessage-routes.db")
        asyncio.run(init_db())
        self.original_token = config.IMESSAGE_BRIDGE_TOKEN
        config.IMESSAGE_BRIDGE_TOKEN = "bridge-token"
        app = FastAPI()
        app.include_router(imessage_router.router)
        app.dependency_overrides[verify_token] = lambda: {"username": "connie"}
        self.client = TestClient(app)

    def tearDown(self):
        config.IMESSAGE_BRIDGE_TOKEN = self.original_token
        self.tempdir.cleanup()

    def test_settings_hide_secret_and_runtime_requires_the_bridge(self):
        saved = self.client.put("/api/settings/imessage", json={
            "enabled": True,
            "project_id": "project-1",
            "project_secret": "super-secret",
            "owner_phone": "+8613800138000",
        })
        self.assertEqual(saved.status_code, 200)
        self.assertNotIn("super-secret", saved.text)
        self.assertTrue(saved.json()["data"]["secret_saved"])
        denied = self.client.get("/api/internal/imessage/runtime")
        self.assertEqual(denied.status_code, 401)
        allowed = self.client.get("/api/internal/imessage/runtime", headers={"X-Remoire-Bridge": "bridge-token"})
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["data"]["project_secret"], "super-secret")

    def test_wechat_channel_is_rejected_and_imessage_requires_a_live_line(self):
        app = FastAPI()
        app.include_router(settings_router.router)
        app.dependency_overrides[verify_token] = lambda: {"username": "connie"}
        client = TestClient(app)
        wechat = client.put("/api/settings/proactive", json={"delivery_channel": "wechat"})
        self.assertEqual(wechat.status_code, 422)
        blocked = client.put("/api/settings/proactive", json={"delivery_channel": "imessage"})
        self.assertEqual(blocked.status_code, 400)
        allowed = client.put("/api/settings/proactive", json={"delivery_channel": "remoire"})
        self.assertEqual(allowed.status_code, 200)


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    unittest.main()
