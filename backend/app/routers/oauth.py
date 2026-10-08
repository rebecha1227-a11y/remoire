"""OAuth metadata, SDK protocol endpoints, and explicit owner consent.

This page is separate from the PWA and never changes its visual design.
"""
import html
import base64
import hmac
import json
import secrets
import time
from urllib.parse import unquote

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route
from starlette.datastructures import FormData
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.register import RegistrationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.provider import construct_redirect_uri
from mcp.server.auth.settings import ClientRegistrationOptions

from app import config
from app.auth import verify_password, login_is_rate_limited, record_login_failure, clear_login_failures
from app.database import get_db
from app.oauth import ISSUER, RESOURCE, SCOPE, METADATA_URL, provider, hashed

COOKIE = '__Host-remoire_oauth_csrf'
HEADERS = {'Cache-Control': 'no-store', 'Pragma': 'no-cache', 'Referrer-Policy': 'no-referrer'}


async def metadata(request):
    return JSONResponse({
        'issuer': ISSUER, 'authorization_endpoint': ISSUER+'/authorize',
        'token_endpoint': ISSUER+'/token', 'registration_endpoint': ISSUER+'/register',
        'revocation_endpoint': ISSUER+'/revoke',
        'response_types_supported': ['code'], 'grant_types_supported': ['authorization_code','refresh_token'],
        'token_endpoint_auth_methods_supported': ['none','client_secret_post','client_secret_basic'],
        'revocation_endpoint_auth_methods_supported': ['none','client_secret_post','client_secret_basic'],
        'scopes_supported': [SCOPE], 'code_challenge_methods_supported': ['S256'],
    }, headers=HEADERS)


async def resource_metadata(request):
    return JSONResponse({'resource': RESOURCE, 'authorization_servers': [ISSUER],
        'scopes_supported': [SCOPE], 'bearer_methods_supported': ['header'],
        'resource_name': 'Remoire private memory'}, headers=HEADERS)


def failure(text, status=400):
    return HTMLResponse('<!doctype html><html lang="zh"><meta charset="utf-8"><title>Remoire 授权</title><p>'
                        + html.escape(text) + '</p></html>', status_code=status, headers=HEADERS)


async def consent(request: Request):
    if request.method == 'GET':
        request_id = request.query_params.get('request_id', '')
        if len(request_id) > 100:
            return failure('授权请求无效，请从 ChatGPT 重新连接。')
        async with get_db() as db:
            row = await (await db.execute('SELECT * FROM oauth_pending WHERE request_hash=? AND expires>?',
                                          (hashed(request_id), int(time.time())))).fetchone()
            if not row:
                return failure('授权请求已过期，请从 ChatGPT 重新连接。')
            csrf = secrets.token_urlsafe(32)
            await db.execute('UPDATE oauth_pending SET csrf_hash=? WHERE request_hash=?', (hashed(csrf), hashed(request_id)))
            await db.commit()
        data = json.loads(row['payload'])
        # Only registered, SDK-validated callback URLs appear here; escape anyway.
        callback = html.escape(data['params']['redirect_uri'])
        body = f'''<!doctype html><html lang="zh"><head><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1"><title>授权 ChatGPT · Remoire</title>
        <style>body{{background:#F6F2ED;color:#28211C;font:17px/1.7 serif;max-width:540px;margin:48px auto;padding:24px}}
        input,button{{box-sizing:border-box;min-height:44px;width:100%;margin:8px 0;padding:10px;font:inherit}}
        button{{background:#7C6350;color:#FAF8F4;border:0}} small{{overflow-wrap:anywhere}}</style></head><body>
        <h1>连接你的 Remoire</h1><p>登录并允许 ChatGPT 通过 MCP 访问这个私人空间。</p>
        <p>授权包含：读取记忆和日记、写入记忆和日记、留下纸条、更新状态和完成事项。
        不包含模型密钥和网页登录管理。</p>
        <p>密码只提交给 remoire.cc，不会发送给 ChatGPT。请只在你主动发起连接时授权。</p>
        <small>授权后返回：{callback}</small>
        <form method="post" action="/oauth/consent">
        <input type="hidden" name="request_id" value="{html.escape(request_id, quote=True)}">
        <input type="hidden" name="csrf" value="{csrf}">
        <label>Remoire 用户名<input name="username" autocomplete="username" maxlength="100"></label>
        <label>Remoire 登录密码<input type="password" name="password" autocomplete="current-password" maxlength="500"></label>
        <button name="decision" value="allow" type="submit">登录并允许访问</button>
        <button name="decision" value="deny" type="submit">取消，不授权</button></form></body></html>'''
        response = HTMLResponse(body, headers=HEADERS)
        response.set_cookie(COOKIE, csrf, secure=True, httponly=True, samesite='lax', max_age=600, path='/')
        return response

    if request.headers.get('origin') != ISSUER:
        return failure('授权来源无效。', 403)
    form = await request.form()
    if any(not isinstance(v, str) for v in form.values()):
        return failure('表单无效。')
    request_id, csrf = form.get('request_id',''), form.get('csrf','')
    if len(request_id) > 100 or not csrf or not hmac.compare_digest(csrf.encode(), request.cookies.get(COOKIE,'').encode()):
        return failure('授权验证失败，请重新连接。', 403)
    async with get_db() as db:
        row = await (await db.execute('SELECT * FROM oauth_pending WHERE request_hash=? AND expires>?',
                                      (hashed(request_id), int(time.time())))).fetchone()
    if not row or not row['csrf_hash'] or not hmac.compare_digest(row['csrf_hash'], hashed(csrf)):
        return failure('授权请求已失效，请重新连接。', 403)
    payload = json.loads(row['payload'])
    params = payload['params']
    decision = form.get('decision')
    if decision not in {'allow','deny'}:
        return failure('请选择是否授权。')
    if decision == 'allow':
        if login_is_rate_limited(request):
            return failure('尝试次数过多，请稍后再试。', 429)
        username, password = form.get('username',''), form.get('password','')
        if len(username) > 100 or len(password) > 500:
            return failure('登录信息过长。')
        valid = verify_password(password, config.APP_PASSWORD_HASH)
        if not (valid and hmac.compare_digest(username.encode(), config.APP_USERNAME.encode())):
            await record_login_failure(request)
            return failure('用户名或密码不正确，请返回上一页重试。', 401)
        clear_login_failures(request)
    code = secrets.token_urlsafe(32)
    async with get_db() as db:
        await db.execute('BEGIN IMMEDIATE')
        result = await db.execute('DELETE FROM oauth_pending WHERE request_hash=? AND csrf_hash=? AND expires>?',
                                  (hashed(request_id), hashed(csrf), int(time.time())))
        if result.rowcount != 1:
            return failure('授权请求已经使用，请重新连接。', 403)
        if decision == 'allow':
            auth_code = {k: params[k] for k in ['scopes','code_challenge','redirect_uri','redirect_uri_provided_explicitly','resource']}
            auth_code.update(client_id=payload['client_id'], expires_at=int(time.time())+120, subject=config.APP_USERNAME)
            await db.execute('INSERT INTO oauth_codes VALUES (?,?,?)', (hashed(code), json.dumps(auth_code), auth_code['expires_at']))
        await db.commit()
    location = construct_redirect_uri(params['redirect_uri'], state=params.get('state'),
                                     **({'code':code} if decision=='allow' else {'error':'access_denied'}))
    response = RedirectResponse(location, status_code=303, headers=HEADERS)
    response.delete_cookie(COOKIE, secure=True, httponly=True, samesite='lax', path='/')
    return response


def bounded(handler, token_endpoint=False, client_endpoint=False):
    async def endpoint(request):
        # Bound form/JSON inputs before SDK handlers read them (also enforced by Nginx).
        body = await request.body()
        if len(body) > 16384 or len(request.scope.get('query_string',b'')) > 8192:
            return JSONResponse({'error':'invalid_request'}, status_code=413, headers=HEADERS)
        if len(request.query_params.multi_items()) != len(request.query_params):
            return JSONResponse({'error':'invalid_request'}, status_code=400, headers=HEADERS)
        if request.method == 'POST' and not request.url.path.endswith('/register'):
            if request.headers.get('content-type','').split(';')[0] != 'application/x-www-form-urlencoded':
                return JSONResponse({'error':'invalid_request'}, status_code=400, headers=HEADERS)
            form = await request.form()
            if len(form.multi_items()) != len(form) or any(not isinstance(v,str) for v in form.values()):
                return JSONResponse({'error':'invalid_request'}, status_code=400, headers=HEADERS)
            # SDK 1.30 requires the form client_id even for HTTP Basic. Normalize
            # the standard Basic-only form; the SDK still verifies both credentials.
            if token_endpoint or client_endpoint:
                header = request.headers.get('authorization','')
                if header.startswith('Basic ') and not form.get('client_id'):
                    try:
                        decoded = base64.b64decode(header[6:], validate=True).decode('utf-8')
                        client_id, _ = decoded.split(':',1)
                        request._form = FormData([*form.multi_items(), ('client_id', unquote(client_id))])
                    except (ValueError, UnicodeError):
                        return JSONResponse({'error':'invalid_client'}, status_code=401, headers=HEADERS)
                # SDK RevocationRequest marks this optional value as required.
                # An empty placeholder never bypasses ClientAuthenticator.
                if client_endpoint:
                    form = await request.form()
                    if 'client_secret' not in form:
                        request._form = FormData([*form.multi_items(), ('client_secret', '')])
        if token_endpoint:
            form = await request.form()
            if form.get('resource') not in (None, RESOURCE):
                return JSONResponse({'error':'invalid_target'}, status_code=400, headers=HEADERS)
            verifier = form.get('code_verifier')
            if verifier is not None:
                import re
                if not isinstance(verifier,str) or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}',verifier):
                    return JSONResponse({'error':'invalid_grant'}, status_code=400, headers=HEADERS)
        try:
            response = await handler(request)
        except (ValueError, TypeError):
            return JSONResponse({'error':'invalid_request'}, status_code=400, headers=HEADERS)
        for k,v in HEADERS.items():
            response.headers[k] = v
        return response
    return endpoint


client_auth = ClientAuthenticator(provider)
routes = [
    Route('/.well-known/oauth-authorization-server', metadata),
    Route('/.well-known/oauth-protected-resource/mcp', resource_metadata),
    Route('/.well-known/oauth-protected-resource', resource_metadata),
    Route('/authorize', bounded(AuthorizationHandler(provider).handle), methods=['GET','POST']),
    Route('/register', bounded(RegistrationHandler(provider, ClientRegistrationOptions(enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE])).handle), methods=['POST']),
    Route('/token', bounded(TokenHandler(provider, client_auth).handle, token_endpoint=True), methods=['POST']),
    Route('/revoke', bounded(RevocationHandler(provider, client_auth).handle, client_endpoint=True), methods=['POST']),
    Route('/oauth/consent', bounded(consent), methods=['GET','POST']),
]
