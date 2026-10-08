import asyncio
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, database
from app.auth import make_password_hash
from app.routers import auth, prompt_profiles
from app.services import prompt_profile_service as profiles
from app.services import chat_service as chat, diary_interaction_service as interaction
from app.services import nudge_service as nudge
from app.scheduler import jobs


class ProfileTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(database, 'DATABASE_PATH', str(Path(self.tmp.name) / 'test.db')))
        await database.init_db()

    async def asyncTearDown(self):
        self.stack.close()
        self.tmp.cleanup()

    async def test_initial_import_is_exact_and_restart_does_not_overwrite_edits(self):
        initial = {p['key']: p for p in await profiles.list_profiles()}
        self.assertEqual(initial['voice']['content'], (profiles.PROMPTS_DIR / 'voice.md').read_text())
        value = '  新表达\r\n第二行\n\n'
        await profiles.save_profile('voice', value, False, 1)
        await database.init_db()
        updated = {p['key']: p for p in await profiles.list_profiles()}
        self.assertEqual(updated['voice']['content'], value)
        self.assertEqual(updated['voice']['version'], 2)
        self.assertTrue(updated['voice']['enabled'])

    async def test_original_and_disabled_scene_never_enter_shared_context(self):
        await profiles.save_profile('original', 'PRIVATE-ORIGINAL-CANARY', True, 1)
        await profiles.save_profile('scene', 'SCENE-CANARY', False, 1)
        self.assertNotIn('CANARY', await profiles.load_shared(scene=True))
        await profiles.save_profile('scene', 'SCENE-CANARY', True, 2)
        self.assertIn('SCENE-CANARY', await profiles.load_shared(scene=True))
        self.assertNotIn('CANARY', await profiles.load_shared())
        self.assertNotIn('PRIVATE-ORIGINAL', await profiles.load_shared(scene=True))
        await profiles.save_profile('scene', 'SCENE-CANARY', False, 3)
        self.assertNotIn('CANARY', await profiles.load_shared(scene=True))
        await profiles.restore_version('original', 2, 2)
        self.assertNotIn('PRIVATE-ORIGINAL', await profiles.load_shared(scene=True))

    async def test_empty_text_stays_empty_and_restore_creates_new_version(self):
        first = await profiles.get_version('voice', 1)
        await profiles.save_profile('voice', '', True, 1)
        await database.init_db()
        self.assertNotIn(first['content'], await profiles.load_shared())
        restored = await profiles.restore_version('voice', 1, 2)
        self.assertEqual(restored['version'], 3)
        self.assertEqual(restored['content'], first['content'])
        self.assertEqual((await profiles.get_version('voice', 2))['content'], '')

    async def test_concurrent_edits_have_one_winner_and_no_orphan_history(self):
        outcomes = await asyncio.gather(
            profiles.save_profile('voice', 'device-a', True, 1),
            profiles.save_profile('voice', 'device-b', True, 1), return_exceptions=True)
        self.assertEqual(sum(isinstance(o, profiles.ProfileConflict) for o in outcomes), 1)
        self.assertEqual(len(await profiles.list_versions('voice')), 2)

    async def test_import_original_is_exact_idempotent_and_will_not_overwrite(self):
        from scripts.import_prompt_original import import_original
        source = Path(self.tmp.name) / 'original.md'
        source.write_bytes('  合成原稿\r\n链接不自动抓取\n'.encode())
        first = await import_original(source)
        second = await import_original(source)
        self.assertEqual(first['version'], second['version'])
        self.assertEqual(first['content'].encode(), source.read_bytes())
        source.write_text('不同的原稿')
        with self.assertRaises(ValueError):
            await import_original(source)

    async def test_all_generated_communication_uses_saved_shared_profile(self):
        await profiles.save_profile('identity', 'IDENTITY-CANARY', True, 1)
        await profiles.save_profile('voice', 'VOICE-CANARY', True, 1)
        await profiles.save_profile('scene', 'SCENE-CANARY', True, 1)
        with patch.object(chat.weather_service, 'get_latest', AsyncMock(return_value=None)), \
             patch.object(interaction, 'decide_unlock_requests', AsyncMock(return_value=[])), \
             patch.object(interaction, 'list_recent_notifications_for_connie', AsyncMock(return_value=[])):
            chat_prompt = await chat._build_system_prompt(scene=True)
            autonomous_prompt = await chat._build_system_prompt()
        for prompt in [chat_prompt, autonomous_prompt]:
            self.assertIn('IDENTITY-CANARY', prompt)
            self.assertIn('VOICE-CANARY', prompt)
        self.assertIn('SCENE-CANARY', chat_prompt)
        self.assertNotIn('SCENE-CANARY', autonomous_prompt)

        model = AsyncMock(return_value=(None, {}))
        with patch.object(interaction.model_settings_service, 'get_model_config_for_slot', model), \
             patch.object(interaction, 'call_llm', AsyncMock(return_value='{"respond":false}')) as llm:
            await interaction.decide_unlock_request({'diary_title':'合成', 'diary_content':'合成', 'content':'合成'})
            self.assert_shared(llm.await_args.args[1])
        with patch.object(interaction, '_safe_get_diary', AsyncMock(return_value={'author':'jinger','title':'合成','content':'合成'})), \
             patch.object(interaction, '_safe_recall_memories', AsyncMock(return_value=[])), \
             patch.object(interaction, '_safe_list_recent_messages', AsyncMock(return_value=[])), \
             patch.object(interaction, '_safe_list_interactions', AsyncMock(return_value=[])), \
             patch.object(interaction.model_settings_service, 'get_model_config_for_slot', model), \
             patch.object(interaction, 'call_llm', AsyncMock(return_value='合成回复')) as llm:
            await interaction.generate_connie_reply('test', 'comment', '合成留言')
            self.assert_shared(llm.await_args.args[1])

        with patch.object(jobs, '_already_wrote_for_date', AsyncMock(return_value=False)), \
             patch.object(jobs, '_get_messages_for_date', AsyncMock(return_value=[{'role':'user','content':'合成'}])), \
             patch.object(jobs, '_get_memories_for_date', AsyncMock(return_value=[])), \
             patch.object(jobs.model_settings_service, 'get_model_config_for_slot', model), \
             patch.object(jobs.diary_service, 'create_diary', AsyncMock()), \
             patch.object(jobs, 'call_llm', AsyncMock(side_effect=['{"write":true}', '合成标题\n\n合成日记'])) as llm:
            await jobs.connie_auto_diary(datetime.now(jobs.BJ_TZ))
            self.assertEqual(llm.await_count, 2)
            self.assert_shared(llm.await_args_list[1].args[1])
            self.assertNotIn('IDENTITY-CANARY', llm.await_args_list[0].args[1][0]['content'])
        with patch.object(jobs, '_get_messages_for_date', AsyncMock(return_value=[{'role':'user','content':'合成'}])), \
             patch.object(jobs.model_settings_service, 'get_model_config_for_slot', model), \
             patch.object(jobs, 'call_llm', AsyncMock(return_value='听歌')) as llm:
            await jobs.generate_breath_state()
            self.assert_shared(llm.await_args.args[1])

        with patch.object(nudge, 'call_llm_with_tools', AsyncMock(return_value={'content':'合成独白'})) as llm:
            await nudge._generate_inner_monologue(None, '今天')
            self.assert_shared(llm.await_args.args[1])

    def assert_shared(self, messages):
        prompt = messages[0]['content']
        self.assertEqual(messages[0]['role'], 'system')
        self.assertIn('IDENTITY-CANARY', prompt)
        self.assertIn('VOICE-CANARY', prompt)
        self.assertNotIn('SCENE-CANARY', prompt)


class ProfileApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stack = ExitStack()
        for target, name, value in [
            (database, 'DATABASE_PATH', str(Path(self.tmp.name) / 'api.db')),
            (config, 'APP_USERNAME', 'profile-test'),
            (config, 'APP_PASSWORD_HASH', make_password_hash('test-profile-password')),
            (config, 'SESSION_COOKIE_SECURE', False),
            (config, 'ALLOW_LEGACY_BEARER', False),
        ]:
            self.stack.enter_context(patch.object(target, name, value))
        asyncio.run(database.init_db())
        app = FastAPI()
        app.include_router(auth.router)
        app.include_router(prompt_profiles.router)
        self.client = TestClient(app)
        self.base = '/api/settings/prompt-profiles'

    def tearDown(self):
        self.client.close()
        self.stack.close()
        self.tmp.cleanup()

    def login(self):
        self.client.post('/api/auth/login', json={'username':'profile-test','password':'test-profile-password'})
        return {'X-CSRF-Token':self.client.cookies.get('remoire_csrf')}

    def test_auth_csrf_private_cache_and_no_model_preview(self):
        self.assertEqual(self.client.get(self.base).status_code, 401)
        self.assertEqual(self.client.get(self.base + '/identity/versions/1').status_code, 401)
        headers = self.login()
        data = {'content':'  合成私有文本\r\n', 'expected_version':1}
        self.assertEqual(self.client.put(self.base + '/voice', json=data).status_code, 403)
        response = self.client.put(self.base + '/voice', headers=headers, json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['content'], data['content'])
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.put(self.base + '/voice', headers=headers, json=data).status_code, 409)
        with patch('app.llm.call_llm', AsyncMock(side_effect=AssertionError('No model preview'))) as llm:
            preview = self.client.get(self.base + '/preview')
            self.assertEqual(preview.status_code, 200)
            self.assertIn(data['content'], preview.json()['data']['content'])
            llm.assert_not_awaited()
        self.assertEqual(self.client.post(self.base + '/voice/restore', json={'version':1,'expected_version':2}).status_code, 403)
        restored = self.client.post(self.base + '/voice/restore', headers=headers, json={'version':1,'expected_version':2})
        self.assertEqual(restored.json()['data']['version'], 3)

    def test_validation_unknown_keys_and_history(self):
        headers = self.login()
        self.assertEqual([p['key'] for p in self.client.get(self.base).json()['data']], ['identity', 'voice', 'scene'])
        self.assertEqual(self.client.get(self.base + '/original/versions').status_code, 404)
        self.assertEqual(self.client.get(self.base + '/original/versions/1').status_code, 404)
        self.assertEqual(self.client.put(self.base + '/original', headers=headers, json={'content':'x','expected_version':1}).status_code, 404)
        self.assertEqual(self.client.put(self.base + '/tagging', headers=headers, json={'content':'x','expected_version':1}).status_code, 404)
        self.assertEqual(self.client.put(self.base + '/voice', headers=headers, json={'content':'x'*60001,'expected_version':1}).status_code, 422)
        self.assertEqual(self.client.get(self.base + '/voice/versions/999').status_code, 404)
        self.assertEqual(len(self.client.get(self.base + '/voice/versions').json()['data']), 1)


if __name__ == '__main__':
    unittest.main()
