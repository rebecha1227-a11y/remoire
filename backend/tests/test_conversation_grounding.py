import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app import database
from app.llm import ModelConfig
from app.services import chat_service as chat, nudge_service as nudge, memory_service as memory
from app.services.autonomous_output import parse_autonomous_reply


class GroundingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(database, 'DATABASE_PATH', str(Path(self.tmp.name) / 'grounding.db'))
        self.db_patch.start()
        await database.init_db()

    async def asyncTearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()

    def test_partial_thought_and_english_labels_are_not_displayed(self):
        self.assertEqual(parse_autonomous_reply({'content': '想喝口茶。\n**Clarifying Current Situation**\n**Refining My Actions**'}), ('', '想喝口茶。'))
        self.assertEqual(parse_autonomous_reply({'content': '<think>分析<message>不能发</message>'}), ('', ''))
        self.assertEqual(parse_autonomous_reply({'content': '等会再说。<message>未完成'}), ('', '等会再说。'))
        self.assertEqual(parse_autonomous_reply({'content': '<message>一</message><message>二</message>'}), ('一\n\n二', ''))

    def test_timestamp_offsets_and_missing_timestamp(self):
        for value in ['2026-10-04T16:05:00Z', '2026-10-05T00:05:00+08:00']:
            result = chat._build_llm_history_with_time_gaps([{'role': 'user', 'content': '今天', 'created_at': value}])
            self.assertIn('2026-10-05 00:05', result[0]['content'])
        msg = {'role': 'user', 'content': '没有时间信息'}
        self.assertEqual(chat._build_llm_history_with_time_gaps([msg]), [msg])

    async def test_autonomous_does_not_publish_provider_reasoning_or_send_think_messages(self):
        response = {
            'content': '想留一点安静的时间。<message>今天过得怎么样？</message>'
                       '<think>**Clarifying Current Situation**<message>不应发送</message></think>',
            'reasoning_content': '**Refining My Actions**\nInternal analysis',
        }
        llm = AsyncMock(return_value=response)
        with ExitStack() as stack:
            for name, value in [('_get_recent_app_activity', ''), ('_get_latest_device_snapshot', ''),
                                ('_get_recent_autonomous_logs', '')]:
                stack.enter_context(patch.object(nudge, name, AsyncMock(return_value=value)))
            stack.enter_context(patch.object(chat, 'get_history', AsyncMock(return_value=[])))
            stack.enter_context(patch.object(chat, '_build_resume_bundle', AsyncMock(return_value='')))
            stack.enter_context(patch.object(chat, '_build_system_prompt', AsyncMock(return_value='test')))
            stack.enter_context(patch.object(memory, 'get_core_memories', AsyncMock(return_value=[])))
            stack.enter_context(patch.object(memory, 'recall', AsyncMock(return_value=[])))
            stack.enter_context(patch.object(nudge.model_settings_service, 'get_model_config_for_slot',
                AsyncMock(return_value=(ModelConfig('https://invalid', 'fake', 'test-model'), {}))))
            stack.enter_context(patch.object(nudge, 'call_llm_with_tools', llm))
            result = await nudge.generate_autonomous_activity('synthetic-conversation')
        self.assertEqual(result['content'], '今天过得怎么样？')
        self.assertEqual(result['thinking'], '想留一点安静的时间。')
        self.assertEqual(result['model'], {'slot': 'daily', 'model_id': 'test-model'})
        self.assertIn('【主动消息触发】', llm.await_args.args[1][0]['content'])

    async def test_fallback_does_not_promote_reasoning_to_monologue(self):
        with patch.object(nudge, 'call_llm_with_tools', AsyncMock(return_value={
            'content': '', 'reasoning_content': '**Processing Recent Input**'
        })), patch('app.llm.call_llm', AsyncMock(return_value='**Processing Recent Input**')):
            result = await nudge._generate_inner_monologue(ModelConfig('', '', 'test'), '今天')
        self.assertEqual(result, '')

    async def test_translation_does_not_promote_reasoning_to_monologue(self):
        with patch.object(nudge, 'call_llm_with_tools', AsyncMock(return_value={
            'content': '', 'reasoning_content': '**Consolidating Information Strategy**'
        })):
            result = await nudge._ensure_chinese_monologue(None, 'I am wondering how this afternoon will turn out.')
        self.assertEqual(result, '')

    def test_history_retains_beijing_calendar_date_and_exact_user_words(self):
        history = [{'role': 'user', 'content': '昨晚哭了，但今天在工作。',
                    'created_at': '2026-10-04T16:05:00'}]
        result = chat._build_llm_history_with_time_gaps(history)
        self.assertIn('2026-10-05 00:05', result[0]['content'])
        self.assertEqual(result[-1], {'role': 'user', 'content': history[0]['content']})

    async def test_runtime_prompt_does_not_treat_consciousness_as_confirmed_fact(self):
        with patch.object(chat.weather_service, 'get_latest', AsyncMock(return_value=None)), \
             patch.object(chat.diary_interaction_service, 'decide_unlock_requests', AsyncMock(return_value=[])), \
             patch.object(chat.diary_interaction_service, 'list_recent_notifications_for_connie', AsyncMock(return_value=[])):
            prompt = await chat._build_system_prompt(recalled_memories=[{
                'content': '她可能还在难过', 'layer': 'consciousness', 'event_date': '2026-10-04'
            }])
        self.assertIn('生活细节与时间线', prompt)
        self.assertIn('主观感受，非用户确认事实', prompt)
        self.assertIn('2026-10-04', prompt)


class CandidateEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = database.DATABASE_PATH
        database.DATABASE_PATH = str(Path(self.tmp.name) / 'test.db')
        await database.init_db()
        async with database.get_db() as db:
            await db.execute("INSERT INTO conversations (id,created_at,updated_at) VALUES ('synthetic','2026-10-05','2026-10-05')")
            await db.commit()

    async def asyncTearDown(self):
        database.DATABASE_PATH = self.original_path
        self.tmp.cleanup()

    async def test_high_confidence_guess_or_assistant_quote_cannot_auto_accept(self):
        candidates = [
            {'content': '她有阿姨', 'confidence': .99, 'evidence_type': 'inferred', 'evidence_quote': ''},
            {'content': '她有室友', 'confidence': .99, 'evidence_type': 'explicit', 'evidence_quote': '室友在家'},
            {'content': '她喜欢茶', 'confidence': .99, 'evidence_type': 'explicit', 'evidence_quote': '我喜欢茶'},
        ]
        with patch.object(memory, 'call_llm', AsyncMock(return_value=json.dumps(candidates))), \
             patch.object(memory, '_is_duplicate', AsyncMock(return_value=False)), \
             patch.object(memory.model_settings_service, 'get_model_config_for_slot', AsyncMock(return_value=(None, {}))), \
             patch.object(memory, 'create_memory', AsyncMock(return_value={'memory': {'id': 'accepted'}})) as create:
            result = await memory.extract_candidates('synthetic', [
                {'role': 'user', 'content': '我喜欢茶'}, {'role': 'assistant', 'content': '室友在家'}])
        self.assertEqual([r['status'] for r in result], ['pending', 'pending', 'accepted'])
        create.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
