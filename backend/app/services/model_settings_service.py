import uuid
import asyncio
import ipaddress
import json
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
DEFAULT_CONTEXT_WINDOW = 32768
DEFAULT_OUTPUT_BUDGET = 4096
MAX_OUTPUT_BUDGET = 524_288


def _positive_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def infer_model_capabilities(model_name: str | None) -> dict | None:
    """Return verified capabilities for model IDs, including gateway aliases."""
    normalized = (model_name or "").lower().replace("_", "-")
    if "claude-opus-4-6" in normalized or "claude-opus-4.6" in normalized:
        return {
            "context_window": 1_000_000,
            "max_output_tokens": 128_000,
            "prompt_caching": True,
            "cache_min_tokens": 4_096,
            "protocol": "anthropic-messages",
            "source": "Anthropic Claude Opus 4.6",
            "source_type": "official-registry",
        }
    if "gemini-2.5-pro" in normalized:
        return {
            "context_window": 1_048_576,
            "max_output_tokens": 65_536,
            "prompt_caching": True,
            "protocol": "openai-compatible",
            "source": "Google Gemini 2.5 Pro",
            "source_type": "official-registry",
        }
    if any(name in normalized for name in (
        "deepseek-flash", "deepseek-v4-flash", "deepseek-v4.1-flash",
        "deepseek-v4-pro", "deepseek-v4.1-pro",
    )):
        return {
            "context_window": 1_000_000,
            "max_output_tokens": 393_216,
            "prompt_caching": True,
            "protocol": "openai-compatible",
            "source": "DeepSeek V4.1 API",
            "source_type": "official-registry",
        }
    return None


def capabilities_from_model_metadata(item: dict | None) -> dict | None:
    """Normalize common /models capability fields without trusting arbitrary payloads."""
    if not isinstance(item, dict):
        return None
    nested = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
    context_window = next((value for value in (
        item.get("context_window"), item.get("max_input_tokens"),
        item.get("input_token_limit"), item.get("inputTokenLimit"),
        nested.get("context_window"), nested.get("max_input_tokens"),
        nested.get("input_token_limit"), nested.get("inputTokenLimit"),
    ) if _positive_int(value)), None)
    max_output_tokens = next((value for value in (
        item.get("max_output_tokens"), item.get("max_tokens"),
        item.get("output_token_limit"), item.get("outputTokenLimit"),
        nested.get("max_output_tokens"), nested.get("max_tokens"),
        nested.get("output_token_limit"), nested.get("outputTokenLimit"),
    ) if _positive_int(value)), None)
    context_window = _positive_int(context_window)
    max_output_tokens = _positive_int(max_output_tokens)
    if not context_window and not max_output_tokens:
        return None
    result = {
        "source": "模型服务 /models 元数据",
        "source_type": "provider-metadata",
    }
    if context_window:
        result["context_window"] = min(context_window, 2_000_000)
    if max_output_tokens:
        result["max_output_tokens"] = min(max_output_tokens, MAX_OUTPUT_BUDGET)
    caching = nested.get("prompt_caching", item.get("prompt_caching"))
    if isinstance(caching, bool):
        result["prompt_caching"] = caching
    return result


def resolve_model_capabilities(model_name: str | None, metadata: dict | None = None) -> dict | None:
    """Prefer provider limits and use the verified registry to fill missing fields."""
    registered = infer_model_capabilities(model_name)
    remote = capabilities_from_model_metadata(metadata)
    if not registered:
        return remote
    if not remote:
        return registered

    resolved = dict(registered)
    for field in ("context_window", "max_output_tokens"):
        if remote.get(field):
            resolved[field] = min(registered.get(field, remote[field]), remote[field])
    if "prompt_caching" in remote:
        resolved["prompt_caching"] = bool(registered.get("prompt_caching") and remote["prompt_caching"])
    resolved["source"] = f"{registered['source']} + 模型服务元数据"
    resolved["source_type"] = "verified-and-provider"
    return resolved


def _normalize_saved_capabilities(value, model_name: str | None = None) -> dict | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            value = None
    remote = capabilities_from_model_metadata(value)
    if isinstance(value, dict) and value.get("context_window"):
        remote = capabilities_from_model_metadata({
            "context_window": value.get("context_window"),
            "max_output_tokens": value.get("max_output_tokens"),
            "prompt_caching": value.get("prompt_caching"),
        })
    return resolve_model_capabilities(model_name, remote) if remote else infer_model_capabilities(model_name)


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
    capabilities = _normalize_saved_capabilities(row["capabilities_json"], row["model_name"])
    return {
        "id": row["id"],
        "nickname": row["nickname"],
        "provider": row["provider"],
        "api_key": _decrypt_api_key(row["api_key"]),
        "base_url": row["base_url"],
        "model_name": row["model_name"],
        "capabilities": capabilities,
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
            """INSERT OR REPLACE INTO model_slots
               (slot, preset_id, extended_thinking, context_window, output_budget, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("daily", preset_id, 0, DEFAULT_CONTEXT_WINDOW, DEFAULT_OUTPUT_BUDGET, now),
        )
        for slot in ("deep", "backend"):
            await db.execute(
                """INSERT OR IGNORE INTO model_slots
                   (slot, preset_id, extended_thinking, context_window, output_budget, updated_at)
                   VALUES (?, NULL, 0, ?, ?, ?)""",
                (slot, DEFAULT_CONTEXT_WINDOW, DEFAULT_OUTPUT_BUDGET, now),
            )
        await db.commit()


async def list_presets() -> list[dict]:
    await seed_env_daily_preset()
    async with get_db() as db:
        async with db.execute(
            """SELECT id, nickname, provider, api_key, base_url, model_name, capabilities_json, created_at, updated_at
               FROM model_presets
               ORDER BY created_at DESC"""
        ) as cur:
            rows = await cur.fetchall()
    return [_public_preset(_row_to_preset(row)) for row in rows]


async def get_preset(preset_id: str) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            """SELECT id, nickname, provider, api_key, base_url, model_name, capabilities_json, created_at, updated_at
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
               (id, nickname, provider, api_key, base_url, model_name, capabilities_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                preset_id,
                data["nickname"].strip(),
                (data.get("provider") or "openai-compatible").strip(),
                _encrypt_api_key(data["api_key"]),
                data["base_url"].strip().rstrip("/"),
                data["model_name"].strip(),
                json.dumps(_normalize_saved_capabilities(data.get("model_capabilities"), data["model_name"]), ensure_ascii=False),
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
    capability_input = (
        data.get("model_capabilities")
        if "model_capabilities" in data
        else current.get("capabilities") if merged["model_name"] == current["model_name"] else None
    )
    now = _now()
    async with get_db() as db:
        await db.execute(
            """UPDATE model_presets
               SET nickname = ?, provider = ?, api_key = ?, base_url = ?, model_name = ?, capabilities_json = ?, updated_at = ?
               WHERE id = ?""",
            (
                merged["nickname"].strip(),
                (merged.get("provider") or "openai-compatible").strip(),
                _encrypt_api_key(merged["api_key"]),
                merged["base_url"].strip().rstrip("/"),
                merged["model_name"].strip(),
                json.dumps(_normalize_saved_capabilities(capability_input, merged["model_name"]), ensure_ascii=False),
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
    result = []
    for item in models:
        if not item.get("id"):
            continue
        model = {"id": item["id"], "owned_by": item.get("owned_by")}
        for field in (
            "max_input_tokens", "max_output_tokens", "max_tokens", "context_window",
            "input_token_limit", "output_token_limit", "inputTokenLimit", "outputTokenLimit",
            "capabilities",
        ):
            if item.get(field) is not None:
                model[field] = item[field]
        capabilities = resolve_model_capabilities(item["id"], item)
        if capabilities:
            model["inferred_capabilities"] = capabilities
        result.append(model)
    return result


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
                """INSERT OR IGNORE INTO model_slots
                   (slot, preset_id, extended_thinking, context_window, output_budget, updated_at)
                   VALUES (?, NULL, 0, ?, ?, ?)""",
                (slot, DEFAULT_CONTEXT_WINDOW, DEFAULT_OUTPUT_BUDGET, now),
            )
        await db.commit()
        async with db.execute(
            """SELECT s.slot, s.preset_id, s.extended_thinking,
                      s.context_window, s.output_budget, s.updated_at,
                      p.nickname, p.provider, p.api_key, p.base_url, p.model_name, p.capabilities_json
               FROM model_slots s
               LEFT JOIN model_presets p ON p.id = s.preset_id
               ORDER BY CASE s.slot WHEN 'daily' THEN 1 WHEN 'deep' THEN 2 ELSE 3 END"""
        ) as cur:
            rows = await cur.fetchall()

    result = []
    for row in rows:
        preset = None
        capabilities = _normalize_saved_capabilities(row["capabilities_json"], row["model_name"])
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
            "context_window": (
                capabilities.get("context_window") if capabilities and capabilities.get("context_window")
                else row["context_window"] or DEFAULT_CONTEXT_WINDOW
            ),
            "output_budget": (
                capabilities.get("max_output_tokens") if capabilities and capabilities.get("max_output_tokens")
                else row["output_budget"] or DEFAULT_OUTPUT_BUDGET
            ),
            "capabilities": capabilities,
            "updated_at": row["updated_at"],
            "preset": preset,
        })
    return result


async def update_slot(
    slot: str,
    preset_id=UNSET,
    extended_thinking=UNSET,
    context_window=UNSET,
    output_budget=UNSET,
) -> dict:
    if slot not in SLOTS:
        raise ValueError("未知模型槽位")

    slots = {item["slot"]: item for item in await list_slots()}
    current = slots.get(slot)
    current_preset_id = current.get("preset_id") if current else None
    next_preset_id = current_preset_id if preset_id is UNSET else preset_id
    if next_preset_id and not await get_preset(next_preset_id):
        raise PresetNotFoundError("模型预设不存在")
    thinking = bool(current["extended_thinking"]) if current and extended_thinking is UNSET else bool(extended_thinking)
    selected_preset = await get_preset(next_preset_id) if next_preset_id else None
    inferred = selected_preset.get("capabilities") if selected_preset else None
    if next_preset_id != current_preset_id:
        current = {**(current or {}), "context_window": DEFAULT_CONTEXT_WINDOW,
                   "output_budget": DEFAULT_OUTPUT_BUDGET}
    next_context_window = (
        inferred.get("context_window") if inferred and inferred.get("context_window") else
        int(current.get("context_window") or DEFAULT_CONTEXT_WINDOW)
        if context_window is UNSET or context_window is None else int(context_window)
    )
    next_output_budget = (
        inferred.get("max_output_tokens") if inferred and inferred.get("max_output_tokens") else
        int(current.get("output_budget") or DEFAULT_OUTPUT_BUDGET)
        if output_budget is UNSET or output_budget is None else int(output_budget)
    )
    if not 8192 <= next_context_window <= 2_000_000:
        raise ValueError("上下文窗口需要在 8,192 到 2,000,000 tokens 之间")
    if not 256 <= next_output_budget <= MAX_OUTPUT_BUDGET:
        raise ValueError(f"单次输出上限需要在 256 到 {MAX_OUTPUT_BUDGET:,} tokens 之间")
    if next_output_budget >= next_context_window:
        raise ValueError("单次输出上限必须小于上下文窗口")
    safety = max(512, min(4096, int(next_context_window * 0.04)))
    if next_context_window - next_output_budget - safety < 1024:
        raise ValueError("上下文窗口扣除回答上限后，至少要给输入保留 1,024 tokens")

    async with get_db() as db:
        await db.execute(
            """INSERT OR REPLACE INTO model_slots
               (slot, preset_id, extended_thinking, context_window, output_budget, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (slot, next_preset_id, int(thinking), next_context_window, next_output_budget, _now()),
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
                provider=preset.get("provider") or "openai-compatible",
                slot=slot,
            ),
            selected,
        )

    return (
        ModelConfig(
            api_base=DAILY_API_BASE,
            api_key=DAILY_API_KEY,
            model_id=DAILY_MODEL_ID,
            slot=slot,
        ),
        {
            "slot": slot,
            "preset_id": None,
            "extended_thinking": False,
            "context_window": DEFAULT_CONTEXT_WINDOW,
            "output_budget": DEFAULT_OUTPUT_BUDGET,
            "preset": None,
        },
    )


async def get_cache_stats(days: int = 7) -> dict:
    """Summarize only provider-reported cache metrics; no prompt content is stored."""
    safe_days = max(1, min(int(days), 90))
    async with get_db() as db:
        async with db.execute(
            """SELECT
                   COUNT(*) AS requests,
                   SUM(CASE WHEN cache_requested = 1 THEN 1 ELSE 0 END) AS cache_requested_requests,
                   SUM(CASE WHEN cache_reported = 1 THEN 1 ELSE 0 END) AS observable_requests,
                   SUM(CASE WHEN cache_reported = 1 AND cache_read_input_tokens > 0 THEN 1 ELSE 0 END) AS hit_requests,
                   SUM(cache_read_input_tokens) AS read_tokens,
                   SUM(cache_creation_input_tokens) AS write_tokens
               FROM llm_usage_events
               WHERE created_at >= datetime('now', ?)""",
            (f"-{safe_days} days",),
        ) as cur:
            row = await cur.fetchone()
    data = {key: int(row[key] or 0) for key in (
        "requests", "cache_requested_requests", "observable_requests", "hit_requests",
        "read_tokens", "write_tokens",
    )}
    data["days"] = safe_days
    data["hit_rate"] = round(
        data["hit_requests"] / data["observable_requests"] * 100, 1
    ) if data["observable_requests"] else None
    return data
