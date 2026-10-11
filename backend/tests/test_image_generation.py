import unittest
from unittest.mock import AsyncMock, patch
import httpx
from app import llm

PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII='

class ImageGenerationProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, provider, result, status=200):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(status, json=result)
        original = httpx.AsyncClient
        def client(**kwargs):
            return original(transport=httpx.MockTransport(handle), **kwargs)
        config = llm.ModelConfig('https://images.example/v1', 'private-key', 'test-model', provider, 'image')
        with patch('app.services.model_settings_service._validated_public_base', AsyncMock(return_value={'base_url':config.api_base})), patch.object(llm.httpx, 'AsyncClient', client):
            image = await llm.generate_image(config, 'A flower')
        return image, requests

    async def test_openai_base64_and_only_drawing_prompt_sent(self):
        image, requests = await self.request('openai-image', {'data':[{'b64_json':PNG}]})
        self.assertTrue(image.startswith('data:image/png;base64,'))
        self.assertEqual(requests[0].url.path, '/v1/images/generations')
        self.assertEqual(requests[0].headers['authorization'], 'Bearer private-key')
        import json
        self.assertEqual(json.loads(requests[0].content), {'model':'test-model', 'prompt':'A flower', 'n':1})

    async def test_gemini_uses_native_endpoint_and_skips_thought_image(self):
        image, requests = await self.request('gemini-image', {'candidates':[{'content':{'parts':[
            {'thought':True, 'inlineData':{'data':'invalid'}}, {'inlineData':{'data':PNG,'mimeType':'image/png'}}]}}]})
        self.assertTrue(image.endswith(PNG))
        self.assertEqual(requests[0].url.path, '/v1/models/test-model:generateContent')
        self.assertEqual(requests[0].headers['x-goog-api-key'], 'private-key')

    async def test_url_only_and_invalid_image_are_not_forwarded(self):
        for result in ({'data':[{'url':'http://localhost/private'}]}, {'data':[{'b64_json':'not-an-image'}]}):
            with self.assertRaises(ValueError):
                await self.request('openai-image', result)

    async def test_https_url_response_is_downloaded_once(self):
        import base64
        requests = []
        def handle(request):
            requests.append(request)
            if request.method == 'POST':
                return httpx.Response(200, json={'data':[{'url':'https://cdn.example/pic.png'}]})
            return httpx.Response(200, content=base64.b64decode(PNG))
        original = httpx.AsyncClient
        def client(**kwargs):
            return original(transport=httpx.MockTransport(handle), **kwargs)
        config = llm.ModelConfig('https://images.example/v1', 'k', 'gpt-image-2.5', 'image', 'image')
        with patch('app.services.model_settings_service._validated_public_base', AsyncMock(return_value={'base_url':config.api_base})), patch.object(llm.httpx, 'AsyncClient', client):
            image = await llm.generate_image(config, 'A flower')
        self.assertTrue(image.startswith('data:image/png;base64,'))
        self.assertEqual([r.method for r in requests], ['POST', 'GET'])

    async def test_http_failure_propagates_without_retry(self):
        with self.assertRaises(llm.ImageProviderHTTPError):
            await self.request('openai-image', {'error':'failure'}, 503)

    async def test_redirect_validates_each_host_without_forwarding_key(self):
        import base64
        seen = []
        def handle(request):
            seen.append(request)
            if request.url.host == 'cdn.example':
                return httpx.Response(302, headers={'location':'https://assets.example/image.png'})
            return httpx.Response(200, content=base64.b64decode(PNG))
        validator = AsyncMock()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with patch('app.services.model_settings_service._validated_public_base', validator):
                result = await llm._download_provider_picture(client,'https://cdn.example/start')
        self.assertEqual(result,PNG)
        self.assertEqual(validator.await_count,2)
        self.assertTrue(all('authorization' not in req.headers for req in seen))

    async def test_redirect_to_private_host_is_rejected_before_second_request(self):
        calls = []
        def handle(request):
            calls.append(request)
            return httpx.Response(302, headers={'location':'https://127.0.0.1/private'})
        async def validate(url):
            if '127.0.0.1' in url:
                raise ValueError('private')
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with patch('app.services.model_settings_service._validated_public_base',validate):
                with self.assertRaises(ValueError):
                    await llm._download_provider_picture(client,'https://cdn.example/start')
        self.assertEqual(len(calls),1)

    async def test_public_error_does_not_expose_provider_body_or_url(self):
        request = httpx.Request('POST','https://example.test/private?key=secret')
        error = httpx.HTTPStatusError('sensitive provider body', request=request, response=httpx.Response(403,request=request))
        wrapper = RuntimeError('private')
        wrapper.__cause__ = error
        code, text = llm.public_model_error(wrapper)
        self.assertEqual(code,'model_access_denied')
        self.assertIn('403',text)
        self.assertNotIn('secret',text)
        self.assertNotIn('private',text)

    async def test_heartbeat_does_not_cancel_generation(self):
        import asyncio
        from app.routers.chat import _with_heartbeat
        async def source():
            await asyncio.sleep(0.025)
            yield {'type':'image','image_id':'one'}
        events = [e async for e in _with_heartbeat(source(),interval=0.005)]
        self.assertIn(None,events)
        self.assertEqual(events[-1],{'type':'image','image_id':'one'})
