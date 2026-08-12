"""Single-user authentication backed by opaque server-side sessions."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import config
from app.database import get_db


_bearer = HTTPBearer(auto_error=False)
_login_failures: dict[str, deque[float]] = defaultdict(deque)
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 5
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_password_hash(password: str) -> str:
    """Return a self-describing scrypt password hash suitable for APP_PASSWORD_HASH."""
    if len(password) < 12:
        raise ValueError("密码至少需要 12 个字符")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return "$".join(
        (
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.urlsafe_b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
        )
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def _client_key(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        trusted_proxy = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        trusted_proxy = False
    if trusted_proxy:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
    return peer


def login_is_rate_limited(request: Request) -> bool:
    now = time.monotonic()
    attempts = _login_failures[_client_key(request)]
    while attempts and now - attempts[0] > _LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    return len(attempts) >= _LOGIN_MAX_FAILURES


async def record_login_failure(request: Request) -> None:
    _login_failures[_client_key(request)].append(time.monotonic())
    await asyncio.sleep(0.35)


def clear_login_failures(request: Request) -> None:
    _login_failures.pop(_client_key(request), None)


async def create_session(request: Request, response: Response, username: str) -> None:
    session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=config.SESSION_TTL_DAYS)
    async with get_db() as db:
        await db.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now.isoformat(),))
        await db.execute(
            """INSERT INTO auth_sessions
               (token_hash, csrf_hash, username, user_agent, created_at, expires_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                _hash_secret(session_token),
                _hash_secret(csrf_token),
                username,
                request.headers.get("user-agent", "")[:500],
                now.isoformat(),
                expires.isoformat(),
                now.isoformat(),
            ),
        )
        await db.commit()
    max_age = config.SESSION_TTL_DAYS * 86400
    response.set_cookie(
        config.SESSION_COOKIE_NAME,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=config.SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        config.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=config.SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


async def delete_session(request: Request, response: Response) -> None:
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if token:
        async with get_db() as db:
            await db.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_hash_secret(token),))
            await db.commit()
    response.delete_cookie(config.SESSION_COOKIE_NAME, path="/", secure=config.SESSION_COOKIE_SECURE, samesite="strict")
    response.delete_cookie(config.CSRF_COOKIE_NAME, path="/", secure=config.SESSION_COOKIE_SECURE, samesite="strict")


async def _session_principal(request: Request) -> dict[str, str] | None:
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        return None
    now = datetime.now(timezone.utc)
    async with get_db() as db:
        async with db.execute(
            "SELECT username, csrf_hash, expires_at, last_seen_at FROM auth_sessions WHERE token_hash = ?",
            (_hash_secret(token),),
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row["expires_at"] <= now.isoformat():
            if row:
                await db.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (_hash_secret(token),))
                await db.commit()
            return None

        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            cookie_csrf = request.cookies.get(config.CSRF_COOKIE_NAME, "")
            header_csrf = request.headers.get("x-csrf-token", "")
            valid_csrf = (
                bool(cookie_csrf)
                and hmac.compare_digest(cookie_csrf, header_csrf)
                and hmac.compare_digest(_hash_secret(cookie_csrf), row["csrf_hash"])
            )
            if not valid_csrf:
                raise HTTPException(status_code=403, detail="CSRF 校验失败")

        try:
            last_seen = datetime.fromisoformat(row["last_seen_at"])
        except ValueError:
            last_seen = now - timedelta(hours=1)
        if now - last_seen > timedelta(minutes=5):
            await db.execute(
                "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
                (now.isoformat(), _hash_secret(token)),
            )
            await db.commit()
    return {"username": row["username"], "auth_type": "session"}


async def verify_token(request: Request) -> dict[str, str]:
    principal = await _session_principal(request)
    if principal:
        return principal

    credentials: HTTPAuthorizationCredentials | None = await _bearer(request)
    if (
        config.ALLOW_LEGACY_BEARER
        and config.API_SECRET_KEY
        and credentials
        and hmac.compare_digest(credentials.credentials, config.API_SECRET_KEY)
    ):
        return {"username": config.APP_USERNAME, "auth_type": "legacy_bearer"}
    raise HTTPException(status_code=401, detail="请先登录", headers={"WWW-Authenticate": "Session"})


async def verify_mcp_token(request: Request) -> dict[str, str]:
    """Verify the independent, high-entropy bearer token used by remote MCP."""
    configured_hash = config.MCP_API_TOKEN_SHA256
    if len(configured_hash) != 64 or any(char not in "0123456789abcdef" for char in configured_hash):
        raise HTTPException(status_code=503, detail="MCP 认证尚未配置")
    credentials: HTTPAuthorizationCredentials | None = await _bearer(request)
    if not credentials or not hmac.compare_digest(
        _hash_secret(credentials.credentials), configured_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="MCP 凭据无效",
            headers={"WWW-Authenticate": 'Bearer realm="remoire-mcp"'},
        )
    return {"username": config.APP_USERNAME, "auth_type": "mcp_bearer"}
