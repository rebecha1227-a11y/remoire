import uuid
import asyncio
import ipaddress
import socket
from datetime import datetime
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import (
    DAILY_API_BASE,
    DAILY_API_KEY,
    DAILY_MODEL_ID,
    MODEL_SECRET_ENCRYPTION_KEYS,
    MODEL_SECRET_ENCRYPTION_REQUIRED,
)
from app.database import get_db
from app.llm import ModelConfig


SLOTS = ("daily", "deep", "backend")
UNSET = object()
_ENCRYPTED_PREFIX = "fernet:v1:"


class PresetNotFoundError(ValueError):
    pass


class UnsafeBaseUrlError(ValueError):
    pass


class SecretEncryptionError(RuntimeError):
    pass


def _secret_cipher() -> MultiFernet | None:
    if not MODEL_SECRET_ENCRYPTION_KEYS:
        if MODEL_SECRET_ENCRYPTION_REQUIRED:
            raise SecretEncryptionError("生产环境必须配置 MODEL_SECRET_ENCRYPTION_KEYS")
        return None
    try:
        return MultiFernet([Fernet(key.strip().encode("ascii")) for key in MODEL_SECRET_ENCRYPTION_KEYS])
    except (ValueError, TypeError) as exc:
        raise SecretEncryptionError("MODEL_SECRET_ENCRYPTION_KEYS 包含无效的 Fernet 密钥") from exc


def _encrypt_api_key(api_key: str) -> str:
    value = api_key.strip()
    if not value or value.startswith(_ENCRYPTED_PREFIX):
        return value
    cipher = _secret_cipher()
    if not cipher:
        return value
    token = cipher.encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_ENCRYPTED_PREFIX}{token}"


def _decrypt_api_key(stored: str) -> str:
    if not stored or not stored.startswith(_ENCRYPTED_PREFIX):
        return stored
    cipher = _secret_cipher()
    if not cipher:
        raise SecretEncryptionError("数据库中的模型密钥已加密，但服务器未配置 MODEL_SECRET_ENCRYPTION_KEYS")
    token = stored[len(_ENCRYPTED_PREFIX):]
    try:
        return cipher.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise SecretEncryptionError("模型密钥无法解密，请检查加密密钥配置") from exc


def _normalize_stored_api_key(stored: str) -> str:
    """Encrypt plaintext or rewrap a token with the first configured rotation key."""
    if not stored:
        return stored
    cipher = _secret_cipher()
    if not cipher:
        return stored
    if not stored.startswith(_ENCRYPTED_PREFIX):
        return _encrypt_api_key(stored)

    token = stored[len(_ENCRYPTED_PREFIX):].encode("ascii")
    primary = Fernet(MODEL_SECRET_ENCRYPTION_KEYS[0].strip().encode("ascii"))
    try:
        primary.decrypt(token)
        return stored
    except InvalidToken:
        try:
            plaintext = cipher.decrypt(token)
        except InvalidToken as exc:
            raise SecretEncryptionError("模型密钥无法解密，请检查加密密钥配置") from exc
        return f"{_ENCRYPTED_PREFIX}{primary.encrypt(plaintext).decode('ascii')}"


def _now() -> str:
    return datetime.utcnow().isoformat()


def _row_to_preset(row) -> dict:
    return {
        "id": row["id"],
        "nickname": row["nickname"],
        "provider": row["provider"],
        "api_key": _decrypt_api_key(row["api_key"]),
        "base_url": row["base_url"],
        "model_name": row["model_name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _public_preset(preset: dict | None) -> dict | None:
    if not preset:
        return None
    public = dict(preset)
    public["api_key"] = "********" if public.get("api_key") else ""
    return public


async def migrate_preset_secrets() -> int:
    """Encrypt legacy plaintext preset keys once a server encryption key is configured."""
    if not _secret_cipher():
        return 0
    async with get_db() as db:
        async with db.execute("SELECT id, api_key FROM model_presets") as cur:
            rows = await cur.fetchall()
        pending = []
        for row in rows:
            normalized = _normalize_stored_api_key(row["api_key"])
            if normalized != row["api_key"]:
                pending.append((row, normalized))
        for row, normalized in pending:
            await db.execute(
                "UPDATE model_presets SET api_key = ?, updated_at = ? WHERE id = ?",
                (normalized, _now(), row["id"]),
            )
        if pending:
            await db.commit()
    return len(pending)


async def _validated_public_base(base_url: str) -> dict:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UnsafeBaseUrlError("拉取模型列表只允许使用 https 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise UnsafeBaseUrlError("API Base URL 不能包含账号、密码、查询参数或片段")

    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise UnsafeBaseUrlError("API Base URL 不能指向本机地址")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip:
        _reject_non_global_ip(ip)
        return {"base_url": parsed.geturl().rstrip("/")}

    try:
        addr_infos = await asyncio.wait_for(
            asyncio.to_thread(socket.getaddrinfo, host, parsed.port, type=socket.SOCK_STREAM),
            timeout=5,
        )
    except socket.gaierror as exc:
        raise UnsafeBaseUrlError(f"API Base URL 域名无法解析：{exc}") from exc
    except asyncio.TimeoutError as exc:
        raise UnsafeBaseUrlError("API Base URL 域名解析超时") from exc

    resolved_ips = {info[4][0] for info in addr_infos}
    if not resolved_ips:
        raise UnsafeBaseUrlError("API Base URL 域名没有可用解析地址")
    parsed_ips = [ipaddress.ip_address(resolved) for resolved in resolved_ips]
    for resolved_ip in parsed_ips:
        _reject_non_global_ip(resolved_ip)
    return {"base_url": parsed.geturl().rstrip("/")}


def _reject_non_global_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if not ip.is_global:
        raise UnsafeBaseUrlError("API Base URL 必须解析到公网地址")


async def _request_openai_compatible(
    api_key: str,
    base_url: str,
    path: str,
    method: str = "GET",
    json: dict | None = None,
) -> dict:
    validated = await _validated_public_base(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    if json is not None:
        headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            method,
            f"{validated['base_url']}{path}",
            headers=headers,
            json=json,
        )
        resp.raise_for_status()
        return resp.json()


async def seed_env_daily_preset() -> None:
    if not DAILY_API_BASE or not DAILY_API_KEY or not DAILY_MODEL_ID:
        return

    async with get_db() as db:
        async with db.execute("SELECT id FROM model_presets LIMIT 1") as cur:
            existing = await cur.fetchone()
        if existing:
            return

        now = _now()
        preset_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO model_presets
               (id, nickname, provider, api_key, base_url, model_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (preset_id, "环境变量默认模型", "openai-compatible", _encrypt_api_key(DAILY_API_KEY), DAILY_API_BASE, DAILY_MODEL_ID, now, now),
        )
        await db.execute(
            """INSERT OR REPLACE INTO model_slots (slot, preset_id, extended_thinking, updated_at)
               VALUES (?, ?, ?, ?)""",
            ("daily", preset_id, 0, now),
        )
        for slot in ("deep", "backend"):
            await db.execute(
                """INSERT OR IGNORE INTO model_slots (slot, preset_id, extended_thinking, updated_at)
                   VALUES (?, NULL, 0, ?)""",
                (slot, now),
            )
        await db.commit()


async def list_presets() -> list[dict]:
    await seed_env_daily_preset()
    async with get_db() as db:
        async with db.execute(
            """SELECT id, nickname, provider, api_key, base_url, model_name, created_at, updated_at
               FROM model_presets
               ORDER BY created_at DESC"""
        ) as cur:
            rows = await cur.fetchall()
    return [_public_preset(_row_to_preset(row)) for row in rows]


async def get_preset(preset_id: str) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            """SELECT id, nickname, provider, api_key, base_url, model_name, created_at, updated_at
               FROM model_presets
               WHERE id = ?""",
            (preset_id,),
        ) as cur:
            row = await cur.fetchone()
    return _row_to_preset(row) if row else None


async def get_public_preset(preset_id: str) -> dict | None:
    return _public_preset(await get_preset(preset_id))


async def create_preset(data: dict) -> dict:
    now = _now()
    preset_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """INSERT INTO model_presets
               (id, nickname, provider, api_key, base_url, model_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                preset_id,
                data["nickname"].strip(),
                (data.get("provider") or "openai-compatible").strip(),
                _encrypt_api_key(data["api_key"]),
                data["base_url"].strip().rstrip("/"),
                data["model_name"].strip(),
                now,
                now,
            ),
        )
        await db.commit()
    return await get_public_preset(preset_id)


async def update_preset(preset_id: str, data: dict) -> dict:
    current = await get_preset(preset_id)
    if not current:
        raise PresetNotFoundError("模型预设不存在")

    merged = {**current, **{k: v for k, v in data.items() if v is not None}}
    now = _now()
    async with get_db() as db:
        await db.execute(
            """UPDATE model_presets
               SET nickname = ?, provider = ?, api_key = ?, base_url = ?, model_name = ?, updated_at = ?
               WHERE id = ?""",
            (
                merged["nickname"].strip(),
                (merged.get("provider") or "openai-compatible").strip(),
                _encrypt_api_key(merged["api_key"]),
                merged["base_url"].strip().rstrip("/"),
                merged["model_name"].strip(),
                now,
                preset_id,
            ),
        )
        await db.commit()
    return await get_public_preset(preset_id)


async def delete_preset(preset_id: str) -> None:
    if not await get_preset(preset_id):
        raise PresetNotFoundError("模型预设不存在")
    async with get_db() as db:
        await db.execute("UPDATE model_slots SET preset_id = NULL, updated_at = ? WHERE preset_id = ?", (_now(), preset_id))
        await db.execute("DELETE FROM model_presets WHERE id = ?", (preset_id,))
        await db.commit()


async def list_remote_models(preset_id: str) -> list[dict]:
    preset = await get_preset(preset_id)
    if not preset:
        raise PresetNotFoundError("模型预设不存在")

    return await list_remote_models_for_config(
        api_key=preset["api_key"],
        base_url=preset["base_url"],
    )


async def list_remote_models_for_config(api_key: str, base_url: str) -> list[dict]:
    payload = await _request_openai_compatible(api_key, base_url, "/models")
    models = payload.get("data", [])
    return [{"id": item.get("id"), "owned_by": item.get("owned_by")} for item in models if item.get("id")]


async def test_model_config(api_key: str, base_url: str, model_name: str) -> dict:
    payload = await _request_openai_compatible(
        api_key,
        base_url,
        "/chat/completions",
        method="POST",
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": "只回复 OK"}],
            "temperature": 0,
            "max_tokens": 8,
            "stream": False,
        },
    )
    reply = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {"reply": reply}


async def test_saved_model_config(preset_id: str) -> dict:
    preset = await get_preset(preset_id)
    if not preset:
        raise PresetNotFoundError("模型预设不存在")
    return await test_model_config(preset["api_key"], preset["base_url"], preset["model_name"])


async def list_slots() -> list[dict]:
    await seed_env_daily_preset()
    now = _now()
    async with get_db() as db:
        for slot in SLOTS:
            await db.execute(
                """INSERT OR IGNORE INTO model_slots (slot, preset_id, extended_thinking, updated_at)
                   VALUES (?, NULL, 0, ?)""",
                (slot, now),
            )
        await db.commit()
        async with db.execute(
            """SELECT s.slot, s.preset_id, s.extended_thinking, s.updated_at,
                      p.nickname, p.provider, p.api_key, p.base_url, p.model_name
               FROM model_slots s
               LEFT JOIN model_presets p ON p.id = s.preset_id
               ORDER BY CASE s.slot WHEN 'daily' THEN 1 WHEN 'deep' THEN 2 ELSE 3 END"""
        ) as cur:
            rows = await cur.fetchall()

    result = []
    for row in rows:
        preset = None
        if row["preset_id"]:
            preset = {
                "id": row["preset_id"],
                "nickname": row["nickname"],
                "provider": row["provider"],
                "base_url": row["base_url"],
                "model_name": row["model_name"],
            }
        result.append({
            "slot": row["slot"],
            "preset_id": row["preset_id"],
            "extended_thinking": bool(row["extended_thinking"]),
            "updated_at": row["updated_at"],
            "preset": preset,
        })
    return result


async def update_slot(slot: str, preset_id=UNSET, extended_thinking=UNSET) -> dict:
    if slot not in SLOTS:
        raise ValueError("未知模型槽位")

    slots = {item["slot"]: item for item in await list_slots()}
    current = slots.get(slot)
    current_preset_id = current.get("preset_id") if current else None
    next_preset_id = current_preset_id if preset_id is UNSET else preset_id
    if next_preset_id and not await get_preset(next_preset_id):
        raise PresetNotFoundError("模型预设不存在")
    thinking = bool(current["extended_thinking"]) if current and extended_thinking is UNSET else bool(extended_thinking)

    async with get_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO model_slots (slot, preset_id, extended_thinking, updated_at)
               VALUES (?, ?, ?, ?)""",
            (slot, next_preset_id, int(thinking), _now()),
        )
        await db.commit()
    return {item["slot"]: item for item in await list_slots()}[slot]


async def get_model_config_for_slot(slot: str = "daily") -> tuple[ModelConfig, dict]:
    slots = {item["slot"]: item for item in await list_slots()}
    selected = slots.get(slot) or slots.get("daily")
    preset = await get_preset(selected["preset_id"]) if selected and selected.get("preset_id") else None

    if preset:
        return (
            ModelConfig(
                api_base=preset["base_url"],
                api_key=preset["api_key"],
                model_id=preset["model_name"],
            ),
            selected,
        )

    return (
        ModelConfig(
            api_base=DAILY_API_BASE,
            api_key=DAILY_API_KEY,
            model_id=DAILY_MODEL_ID,
        ),
        {
            "slot": slot,
            "preset_id": None,
            "extended_thinking": False,
            "preset": None,
        },
    )
