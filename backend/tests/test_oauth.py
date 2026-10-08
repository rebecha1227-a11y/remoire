"""Isolated OAuth protocol tests. Never touch the production database or LLM."""
import asyncio
import base64
import hashlib
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from app import config, database
from app.auth import make_password_hash, verify_mcp_token
from app.oauth import ISSUER, RESOURCE, provider, hashed
from app.routers.oauth import routes
from app.services import model_settings_service as secrets_service


class OAuthTests(unittest.TestCase):
    callback = 'https://chatgpt.com/connector_platform_oauth_redirect'
    password = 'test-only-correct-password'
    verifier = 'A' * 64

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbpath = str(Path(self.tmp.name) / 'test.db')
        self.patches = [patch.object(database, 'DATABASE_PATH', self.dbpath),
            patch.object(config, 'APP_USERNAME', 'oauth-test-owner'),
            patch.object(config, 'APP_PASSWORD_HASH', make_password_hash(self.password)),
            patch.object(config, 'MCP_API_TOKEN_SHA256', hashed('codex-test-token')),
            patch.object(secrets_service, 'MODEL_SECRET_ENCRYPTION_KEYS', [Fernet.generate_key().decode()])]
        for p in self.patches:
            p.start()
        asyncio.run(database.init_db())
        app = FastAPI()
        app.router.routes.extend(routes)

        @app.get('/probe')
        async def probe(_=Depends(verify_mcp_token)):
            return {'ok': True}

        self.client = TestClient(app, base_url=ISSUER, follow_redirects=False)

    def tearDown(self):
        self.client.close()
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def register(self, method='none', callback=None):
        r = self.client.post('/register', json={'redirect_uris':[callback or self.callback],
            'token_endpoint_auth_method':method, 'grant_types':['authorization_code','refresh_token'],
            'response_types':['code'], 'scope':'remoire'})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def pending(self, client):
        r = self.client.get('/authorize', params={'client_id':client['client_id'],
            'redirect_uri':client['redirect_uris'][0], 'response_type':'code', 'scope':'remoire',
            'state':'test-state', 'resource':RESOURCE, 'code_challenge_method':'S256',
            'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')})
        self.assertIn(r.status_code, (302,303,307), r.text)
        page = self.client.get(r.headers['location'])
        self.assertEqual(page.status_code, 200)
        return {k:re.search('name="'+k+'" value="([^"]+)"',page.text)[1] for k in ['request_id','csrf']}

    def consent(self, form, **overrides):
        return self.client.post('/oauth/consent', headers={'Origin':ISSUER},
            data={**form, 'username':config.APP_USERNAME, 'password':self.password, 'decision':'allow', **overrides})

    def code(self, client):
        r = self.consent(self.pending(client))
        self.assertEqual(r.status_code, 303, r.text)
        query = parse_qs(urlsplit(r.headers['location']).query)
        self.assertEqual(query['state'], ['test-state'])
        return query['code'][0]

    def exchange(self, client, code, **overrides):
        data = {'grant_type':'authorization_code','client_id':client['client_id'],
            'code':code,'redirect_uri':client['redirect_uris'][0], 'code_verifier':self.verifier,'resource':RESOURCE,
            **overrides}
        if client.get('client_secret'):
            data['client_secret'] = client['client_secret']
        return self.client.post('/token', data=data)

    def grant(self, method='none'):
        client = self.register(method)
        r = self.exchange(client,self.code(client))
        self.assertEqual(r.status_code,200,r.text)
        return client,r.json()

    def probe(self, token):
        return self.client.get('/probe',headers={'Authorization':'Bearer '+token}).status_code

    def test_metadata_and_existing_codex_token(self):
        r = self.client.get('/.well-known/oauth-authorization-server')
        self.assertEqual(r.json()['code_challenge_methods_supported'], ['S256'])
        self.assertEqual(self.client.get('/.well-known/oauth-protected-resource/mcp').json()['resource'],RESOURCE)
        self.assertEqual(self.probe('codex-test-token'),200)
        self.assertEqual(self.probe('wrong'),401)
        self.assertIn('resource_metadata',self.client.get('/probe').headers['www-authenticate'])

    def test_callback_allowlist(self):
        for uri in ['https://evil.test/callback','http://chatgpt.com/connector_platform_oauth_redirect',
                    'https://chatgpt.com/redirect?to=https://evil.test',
                    self.callback+'?to=bad', self.callback+'#fragment',
                    'https://user@chatgpt.com/connector_platform_oauth_redirect']:
            with self.subTest(uri=uri):
                r=self.client.post('/register',json={'redirect_uris':[uri],
                    'grant_types':['authorization_code','refresh_token']})
                self.assertEqual(r.status_code,400)
        self.register(callback='https://chatgpt.com/connector/oauth/abc-123_def')

    def test_full_grant_and_hashed_encrypted_storage(self):
        client,tokens=self.grant('client_secret_post')
        self.assertEqual(self.probe(tokens['access_token']),200)
        self.assertEqual(self.probe(tokens['refresh_token']),401)
        with sqlite3.connect(self.dbpath) as db:
            dump='\n'.join(db.iterdump())
        for secret in [tokens['access_token'],tokens['refresh_token'],client['client_secret']]:
            self.assertNotIn(secret,dump)
        self.assertIn('fernet:v1:',dump)

    def test_pkce_audience_redirect_and_code_reuse(self):
        c=self.register(); code=self.code(c)
        for overrides in [{'code_verifier':'B'*64},{'resource':'https://evil.test/mcp'},
                          {'redirect_uri':'https://chatgpt.com/connector/oauth/different'}]:
            self.assertEqual(self.exchange(c,code,**overrides).status_code,400)
        self.assertEqual(self.exchange(c,code).status_code,200)
        self.assertEqual(self.exchange(c,code).status_code,400)

    def test_csrf_password_and_consent_replay(self):
        c=self.register(); form=self.pending(c)
        self.assertEqual(self.client.post('/oauth/consent',data=form).status_code,403)
        self.assertEqual(self.consent(form,csrf='bad').status_code,403)
        self.assertEqual(self.consent(form,password='wrong').status_code,401)
        self.assertEqual(self.consent(form).status_code,303)
        self.assertEqual(self.consent(form).status_code,403)

    def test_denial_has_no_code(self):
        r=self.consent(self.pending(self.register()),decision='deny')
        self.assertEqual(r.status_code,303)
        query=parse_qs(urlsplit(r.headers['location']).query)
        self.assertEqual(query['error'],['access_denied']); self.assertNotIn('code',query)

    def test_refresh_rotation_and_reuse_revokes_family(self):
        c,t=self.grant()
        data={'grant_type':'refresh_token','client_id':c['client_id'],'refresh_token':t['refresh_token'],'resource':RESOURCE}
        r=self.client.post('/token',data=data)
        self.assertEqual(r.status_code,200,r.text)
        new=r.json()
        self.assertEqual(self.probe(t['access_token']),401)
        self.assertEqual(self.probe(new['access_token']),200)
        self.assertEqual(self.client.post('/token',data=data).status_code,400)
        self.assertEqual(self.probe(new['access_token']),401)

    def test_revocation(self):
        c,t=self.grant()
        r=self.client.post('/revoke',data={'client_id':c['client_id'],'token':t['refresh_token']})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.probe(t['access_token']),401)

    def test_basic_without_form_client_id(self):
        c=self.register('client_secret_basic'); code=self.code(c)
        r=self.client.post('/token',auth=(c['client_id'],c['client_secret']),data={
            'grant_type':'authorization_code','code':code,'redirect_uri':self.callback,'code_verifier':self.verifier})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.probe(r.json()['access_token']),200)

    def test_expiry_and_cross_client(self):
        c=self.register(); code=self.code(c); other=self.register()
        self.assertEqual(self.exchange(other,code).status_code,400)
        t=self.exchange(c,code).json()
        with sqlite3.connect(self.dbpath) as db:
            db.execute("UPDATE oauth_tokens SET expires=0")
        self.assertEqual(self.probe(t['access_token']),401)
        self.assertEqual(self.client.post('/token',data={'client_id':c['client_id'],
            'grant_type':'refresh_token','refresh_token':t['refresh_token']}).status_code,400)

    def test_duplicate_and_oversized_inputs(self):
        self.assertEqual(self.client.post('/token',content='client_id=a&client_id=b',
            headers={'Content-Type':'application/x-www-form-urlencoded'}).status_code,400)
        self.assertEqual(self.client.get('/authorize?client_id=a&client_id=b').status_code,400)
        self.assertEqual(self.client.post('/register',content='x'*17000).status_code,413)

    def test_concurrent_code_exchange_single_use(self):
        c=self.register(); code=self.code(c)
        async def race():
            client=await provider.get_client(c['client_id'])
            loaded=await provider.load_authorization_code(client,code)
            return await asyncio.gather(provider.exchange_authorization_code(client,loaded),
                provider.exchange_authorization_code(client,loaded),return_exceptions=True)
        results=asyncio.run(race())
        self.assertEqual(sum(not isinstance(r,Exception) for r in results),1)
