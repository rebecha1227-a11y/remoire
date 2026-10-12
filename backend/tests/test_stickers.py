import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from zipfile import ZipFile
from app import database
from app.services import sticker_service as stickers

PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII='

class StickerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(database, 'DATABASE_PATH', str(Path(self.tmp.name)/'test.db'))
        self.cache = patch.object(stickers, 'CACHE_DIR', Path(self.tmp.name)/'cache')
        self.db.start(); self.cache.start()
        await database.init_db()

    async def asyncTearDown(self):
        self.cache.stop(); self.db.stop(); self.tmp.cleanup()

    def document(self, text):
        path = Path(self.tmp.name)/'test.docx'
        with ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>小狗：</w:t></w:r></w:p><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:body></w:document>')
        return path

    async def test_import_glued_links_and_repeat_is_idempotent(self):
        rows = stickers.parse_docx(self.document('开心：https://iili.io/a.gif摸摸：https://iili.io/b.md.jpg'))
        self.assertEqual([r['label'] for r in rows], ['开心','摸摸'])
        await stickers.import_catalogue(rows); await stickers.import_catalogue(rows)
        self.assertEqual(len(await stickers.search('小狗')),2)
        self.assertTrue(await stickers.available())

    async def test_send_requires_search_and_caches_without_generation(self):
        await stickers.import_catalogue(stickers.parse_docx(self.document('开心：https://iili.io/a.gif')))
        turn={}
        self.assertIn('先搜索', await stickers.handle_tool('send_sticker', {'sticker_id':'arbitrary'},turn))
        await stickers.handle_tool('search_stickers', {'query':'开心'},turn)
        key=next(iter(turn['sticker_candidates']))
        download=AsyncMock(return_value=PNG)
        with patch('app.llm._download_provider_picture',download):
            await stickers.handle_tool('send_sticker',{'sticker_id':key},turn)
            self.assertTrue(turn['generated_image'].startswith('data:image/png;base64,'))
            second={'sticker_candidates':{key}}
            await stickers.handle_tool('send_sticker',{'sticker_id':key},second)
            download.assert_awaited_once()
        self.assertIn('不重复',await stickers.handle_tool('send_sticker',{'sticker_id':key},turn))

    async def test_bad_media_is_not_published(self):
        await stickers.import_catalogue(stickers.parse_docx(self.document('开心：https://iili.io/a.gif')))
        turn={}; await stickers.handle_tool('search_stickers',{'query':'开心'},turn)
        key=next(iter(turn['sticker_candidates']))
        with patch('app.llm._download_provider_picture',AsyncMock(return_value=base64.b64encode(b'<html>bad</html>').decode())):
            result=await stickers.handle_tool('send_sticker',{'sticker_id':key},turn)
        self.assertIn('失败',result);self.assertNotIn('generated_image',turn)

    def test_private_url_is_rejected(self):
        with self.assertRaises(ValueError):
            stickers.parse_docx(self.document('开心：https://127.0.0.1/a.gif'))

    async def test_web_catalogue_pagination_and_filter(self):
        await stickers.import_catalogue(stickers.parse_docx(self.document('开心：https://iili.io/a.gif摸摸：https://iili.io/b.jpg')))
        page = await stickers.list_catalogue(limit=1)
        self.assertEqual(page['total'], 2)
        self.assertEqual(len(page['items']), 1)
        self.assertNotIn('source_url', page['items'][0])
        other = await stickers.list_catalogue(offset=1, limit=1)
        self.assertNotEqual(page['items'][0]['id'], other['items'][0]['id'])
        self.assertEqual((await stickers.list_catalogue(query='摸摸'))['total'], 1)
        self.assertEqual((await stickers.list_catalogue(category='不存在'))['total'], 0)

    async def test_web_send_uses_authoritative_label_and_original_media(self):
        from app.routers import chat
        await stickers.import_catalogue(stickers.parse_docx(self.document('开心：https://iili.io/a.gif')))
        key = (await stickers.list_catalogue())['items'][0]['id']
        seen = {}
        async def fake_stream(conversation, message, **kwargs):
            seen.update(message=message, **kwargs)
            yield '收到'
        with patch('app.llm._download_provider_picture', AsyncMock(return_value=PNG)), patch.object(chat, 'stream_chat', fake_stream):
            response = await chat.send_message(chat.SendRequest(message='伪造描述', sticker_id=key))
            async for _ in response.body_iterator:
                pass
        self.assertEqual(seen['message'], '[表情包：开心]')
        self.assertEqual(seen['user_image_kind'], 'sticker')
        self.assertEqual(seen['image'], 'data:image/png;base64,' + PNG)
