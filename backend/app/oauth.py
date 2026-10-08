"""Single-owner MCP OAuth provider using the MCP SDK's protocol handlers.

Opaque credentials are hashed at rest; client secrets use existing encryption.
Only HTTPS ChatGPT callbacks may register. No client-supplied URL is fetched.
"""
import hashlib
import json
import re
import secrets
import time
from urllib.parse import urlsplit

from mcp.server.auth.provider import (
    AccessToken, AuthorizationCode, AuthorizationParams, AuthorizeError,
    RefreshToken, RegistrationError, TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from app import config
from app.database import get_db
from app.services.model_settings_service import _encrypt_api_key, _decrypt_api_key

ISSUER = 'https://remoire.cc'
RESOURCE = ISSUER + '/mcp'
SCOPE = 'remoire'
METADATA_URL = ISSUER + '/.well-known/oauth-protected-resource/mcp'
ACCESS_TTL = 3600
GRANT_TTL = 30 * 86400


def hashed(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def init_oauth_db():
    async with get_db() as db:
        await db.executescript('''
            CREATE TABLE IF NOT EXISTS oauth_clients (
                client_id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS oauth_pending (
                request_hash TEXT PRIMARY KEY, payload TEXT NOT NULL,
                csrf_hash TEXT, expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS oauth_codes (
                code_hash TEXT PRIMARY KEY, payload TEXT NOT NULL, expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                token_hash TEXT PRIMARY KEY, kind TEXT NOT NULL,
                client_id TEXT NOT NULL, family TEXT NOT NULL,
                resource TEXT NOT NULL, scopes TEXT NOT NULL,
                expires INTEGER NOT NULL, family_expires INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS idx_oauth_family ON oauth_tokens(family);
        ''')
        await db.commit()


class RemoireOAuthProvider:
    async def get_client(self, client_id: str):
        if len(client_id) > 200:
            return None
        async with get_db() as db:
            row = await (await db.execute('SELECT metadata FROM oauth_clients WHERE client_id=?', (client_id,))).fetchone()
        if not row:
            return None
        data = json.loads(row['metadata'])
        if data.get('client_secret'):
            data['client_secret'] = _decrypt_api_key(data['client_secret'])
        return OAuthClientInformationFull.model_validate(data)

    async def register_client(self, client_info: OAuthClientInformationFull):
        uris = client_info.redirect_uris or []
        if not 1 <= len(uris) <= 8:
            raise RegistrationError('invalid_redirect_uri', 'Register 1 to 8 ChatGPT HTTPS callbacks')
        for uri in uris:
            parsed = urlsplit(str(uri))
            if (parsed.scheme != 'https' or parsed.hostname not in {'chatgpt.com', 'chat.openai.com'}
                    or parsed.username or parsed.password or parsed.port not in (None, 443)
                    or parsed.fragment or parsed.query or len(str(uri)) > 2048
                    or not (parsed.path == '/connector_platform_oauth_redirect'
                            or re.fullmatch(r'/connector/oauth/[A-Za-z0-9_-]+', parsed.path))):
                raise RegistrationError('invalid_redirect_uri', 'Only ChatGPT HTTPS callbacks are allowed')
        if client_info.token_endpoint_auth_method not in {'none', 'client_secret_post', 'client_secret_basic'}:
            raise RegistrationError('invalid_client_metadata', 'Unsupported authentication method')
        if set(client_info.grant_types) != {'authorization_code', 'refresh_token'} or client_info.response_types != ['code']:
            raise RegistrationError('invalid_client_metadata', 'Only authorization code and refresh grants are supported')
        data = client_info.model_dump(mode='json')
        if data.get('client_secret'):
            data['client_secret'] = _encrypt_api_key(data['client_secret'])
        if len(json.dumps(data)) > 16384:
            raise RegistrationError('invalid_client_metadata', 'Metadata too large')
        async with get_db() as db:
            await db.execute('BEGIN IMMEDIATE')
            count = (await (await db.execute('SELECT COUNT(*) FROM oauth_clients')).fetchone())[0]
            if count >= 1000:
                raise RegistrationError('invalid_client_metadata', 'Registration capacity reached')
            await db.execute('INSERT INTO oauth_clients VALUES (?,?)', (client_info.client_id, json.dumps(data)))
            await db.commit()

    async def authorize(self, client, params: AuthorizationParams):
        if params.resource not in (None, RESOURCE):
            raise AuthorizeError('invalid_request', 'Invalid resource')
        if set(params.scopes or [SCOPE]) != {SCOPE}:
            raise AuthorizeError('invalid_scope', 'Unsupported scope')
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', params.code_challenge):
            raise AuthorizeError('invalid_request', 'S256 PKCE is required')
        if params.state is not None and len(params.state) > 2048:
            raise AuthorizeError('invalid_request', 'State too large')
        params.resource = RESOURCE
        params.scopes = [SCOPE]
        request_id = secrets.token_urlsafe(32)
        payload = {'client_id': client.client_id, 'params': params.model_dump(mode='json')}
        async with get_db() as db:
            await db.execute('BEGIN IMMEDIATE')
            now = int(time.time())
            await db.execute('DELETE FROM oauth_pending WHERE expires<=?', (now,))
            await db.execute('DELETE FROM oauth_codes WHERE expires<=?', (now,))
            await db.execute('DELETE FROM oauth_tokens WHERE family_expires<=?', (now,))
            if (await (await db.execute('SELECT COUNT(*) FROM oauth_pending')).fetchone())[0] >= 200:
                raise AuthorizeError('temporarily_unavailable', 'Please retry later')
            await db.execute('INSERT INTO oauth_pending VALUES (?,?,NULL,?)',
                             (hashed(request_id), json.dumps(payload), now + 600))
            await db.commit()
        return ISSUER + '/oauth/consent?request_id=' + request_id

    async def load_authorization_code(self, client, authorization_code):
        async with get_db() as db:
            row = await (await db.execute('SELECT payload,expires FROM oauth_codes WHERE code_hash=?', (hashed(authorization_code),))).fetchone()
        if not row or row['expires'] <= time.time():
            return None
        data = json.loads(row['payload'])
        if data['client_id'] != client.client_id:
            return None
        return AuthorizationCode(code=authorization_code, **data)

    async def _issue(self, db, client_id, family, family_expires):
        now = int(time.time())
        access, refresh = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        access_expiry = min(now + ACCESS_TTL, family_expires)
        for token, kind, expiry in [(access, 'access', access_expiry), (refresh, 'refresh', family_expires)]:
            await db.execute('''INSERT INTO oauth_tokens
                (token_hash,kind,client_id,family,resource,scopes,expires,family_expires)
                VALUES (?,?,?,?,?,?,?,?)''',
                (hashed(token), kind, client_id, family, RESOURCE, json.dumps([SCOPE]), expiry, family_expires))
        return OAuthToken(access_token=access, token_type='Bearer', expires_in=access_expiry-now,
                          refresh_token=refresh, scope=SCOPE)

    async def exchange_authorization_code(self, client, authorization_code):
        async with get_db() as db:
            await db.execute('BEGIN IMMEDIATE')
            result = await db.execute('DELETE FROM oauth_codes WHERE code_hash=? AND expires>?',
                                      (hashed(authorization_code.code), int(time.time())))
            if result.rowcount != 1:
                raise TokenError('invalid_grant', 'Code expired or already used')
            tokens = await self._issue(db, client.client_id, secrets.token_hex(24), int(time.time()) + GRANT_TTL)
            await db.commit()
            return tokens

    async def load_access_token(self, token):
        if not isinstance(token, str) or len(token) > 256:
            return None
        async with get_db() as db:
            row = await (await db.execute('''SELECT * FROM oauth_tokens WHERE token_hash=?
                AND kind='access' AND revoked=0 AND expires>?''', (hashed(token), int(time.time())))).fetchone()
        if not row or row['resource'] != RESOURCE or json.loads(row['scopes']) != [SCOPE]:
            return None
        return AccessToken(token=token, client_id=row['client_id'], scopes=[SCOPE],
                           expires_at=row['expires'], resource=RESOURCE, subject=config.APP_USERNAME)

    async def load_refresh_token(self, client, refresh_token):
        async with get_db() as db:
            await db.execute('BEGIN IMMEDIATE')
            row = await (await db.execute("SELECT * FROM oauth_tokens WHERE token_hash=? AND kind='refresh' AND client_id=?",
                                          (hashed(refresh_token), client.client_id))).fetchone()
            if not row or row['expires'] <= time.time():
                return None
            if row['used']:
                await db.execute('UPDATE oauth_tokens SET revoked=1 WHERE family=?', (row['family'],))
                await db.commit()
                return None
            if row['revoked']:
                return None
        return RefreshToken(token=refresh_token, client_id=client.client_id, scopes=[SCOPE],
                            expires_at=row['expires'], subject=config.APP_USERNAME)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        if set(scopes) != {SCOPE}:
            raise TokenError('invalid_scope', 'Unsupported scope')
        async with get_db() as db:
            await db.execute('BEGIN IMMEDIATE')
            row = await (await db.execute("SELECT * FROM oauth_tokens WHERE token_hash=? AND kind='refresh' AND client_id=?",
                                          (hashed(refresh_token.token), client.client_id))).fetchone()
            if not row or row['expires'] <= time.time():
                raise TokenError('invalid_grant', 'Expired refresh token')
            if row['used'] or row['revoked']:
                await db.execute('UPDATE oauth_tokens SET revoked=1 WHERE family=?', (row['family'],))
                await db.commit()
                raise TokenError('invalid_grant', 'Refresh token reuse detected')
            await db.execute('UPDATE oauth_tokens SET used=1 WHERE token_hash=?', (hashed(refresh_token.token),))
            await db.execute("UPDATE oauth_tokens SET revoked=1 WHERE family=? AND kind='access'", (row['family'],))
            tokens = await self._issue(db, client.client_id, row['family'], row['family_expires'])
            await db.commit()
            return tokens

    async def revoke_token(self, token):
        async with get_db() as db:
            await db.execute('''UPDATE oauth_tokens SET revoked=1 WHERE family IN
                (SELECT family FROM oauth_tokens WHERE token_hash=?)''', (hashed(token.token),))
            await db.commit()


provider = RemoireOAuthProvider()
