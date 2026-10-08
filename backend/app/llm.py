import httpx
import json as json_mod
import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator


logger = logging.getLogger(__name__)


class UnsupportedAnthropicProtocol(RuntimeError):
    """The configured gateway does not expose an Anthropic Messages endpoint."""

@dataclass
class ModelConfig:
    api_base: str
    api_key: str
    model_id: str
    provider: str = "openai-compatible"
    slot: str = "unknown"


def _is_claude(config: ModelConfig) -> bool:
    return "claude" in (config.model_id or "").lower()


def _openai_headers(config: ModelConfig) -> dict:
    return {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }


def _anthropic_headers(config: ModelConfig) -> dict:
    return {
        "Authorization": f"Bearer {config.api_key}",
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }


def _openai_messages(messages: list[dict]) -> list[dict]:
    """Remove Remoire-only cache annotations before OpenAI-compatible fallback."""
    cleaned = []
    for message in messages:
        item = dict(message)
        item.pop("cache_control", None)
        for key in list(item):
            if key.startswith("_"):
                item.pop(key, None)
        cleaned.append(item)
    return cleaned


def _anthropic_content_blocks(content) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    if not isinstance(content, list):
        return []

    blocks = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text":
            if part.get("text"):
                blocks.append({"type": "text", "text": part["text"]})
        elif part_type == "image_url":
            url = (part.get("image_url") or {}).get("url", "")
            if url.startswith("data:") and ";base64," in url:
                header, data = url.split(",", 1)
                media_type = header[5:].split(";", 1)[0] or "image/jpeg"
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                })
            elif url:
                blocks.append({"type": "image", "source": {"type": "url", "url": url}})
        elif part_type in ("image", "document", "text"):
            blocks.append(dict(part))
    return blocks


def _append_anthropic_message(target: list[dict], role: str, blocks: list[dict]) -> None:
    if not blocks:
        return
    if target and target[-1]["role"] == role:
        target[-1]["content"].extend(blocks)
    else:
        target.append({"role": role, "content": blocks})


def _anthropic_tools(tools: list[dict] | None) -> list[dict]:
    converted = []
    for tool in tools or []:
        fn = tool.get("function") or {}
        if not fn.get("name"):
            continue
        item = {
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
        }
        converted.append(item)
    return converted


def _anthropic_payload(
    config: ModelConfig,
    messages: list[dict],
    *,
    stream: bool,
    temperature: float,
    max_tokens: int,
    tools: list[dict] | None,
    extended_thinking: bool,
) -> dict:
    system_blocks = []
    converted_messages = []
    message_history_started = False

    for message in messages:
        role = message.get("role")
        if role == "system" and not message_history_started:
            text = message.get("content") or ""
            if isinstance(text, str) and text:
                block = {"type": "text", "text": text}
                if message.get("cache_control"):
                    block["cache_control"] = dict(message["cache_control"])
                system_blocks.append(block)
            continue

        message_history_started = True
        if role == "system":
            _append_anthropic_message(
                converted_messages,
                "user",
                [{"type": "text", "text": f"【系统时间线注记】\n{message.get('content') or ''}"}],
            )
        elif role == "tool":
            _append_anthropic_message(converted_messages, "user", [{
                "type": "tool_result",
                "tool_use_id": message.get("tool_call_id", ""),
                "content": str(message.get("content") or ""),
            }])
        elif role == "assistant":
            if message.get("_anthropic_content"):
                # Thinking signatures must be sent back unchanged during tool loops.
                blocks = [dict(block) for block in message["_anthropic_content"]]
            else:
                blocks = _anthropic_content_blocks(message.get("content"))
                for tool_call in message.get("tool_calls") or []:
                    fn = tool_call.get("function") or {}
                    try:
                        tool_input = json_mod.loads(fn.get("arguments") or "{}")
                    except (TypeError, json_mod.JSONDecodeError):
                        tool_input = {}
                    blocks.append({
                        "type": "tool_use",
                        "id": tool_call.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": tool_input if isinstance(tool_input, dict) else {},
                    })
            _append_anthropic_message(converted_messages, "assistant", blocks)
        else:
            _append_anthropic_message(
                converted_messages,
                "user",
                _anthropic_content_blocks(message.get("content")),
            )

    payload = {
        "model": config.model_id,
        "max_tokens": max_tokens,
        "stream": stream,
        "system": system_blocks,
        "messages": converted_messages,
    }
    converted_tools = _anthropic_tools(tools)
    if converted_tools:
        payload["tools"] = converted_tools
    if extended_thinking:
        payload["thinking"] = {"type": "adaptive"}
    else:
        payload["temperature"] = temperature
    return payload


def _anthropic_response_message(data: dict) -> dict:
    text_parts = []
    thinking_parts = []
    tool_calls = []
    for block in data.get("content") or []:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text" and block.get("text"):
            text_parts.append(block["text"])
        elif block_type in ("thinking", "reasoning") and block.get("thinking"):
            thinking_parts.append(block["thinking"])
        elif block_type == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json_mod.dumps(block.get("input") or {}, ensure_ascii=False),
                },
            })
    finish_map = {"end_turn": "stop", "tool_use": "tool_calls", "max_tokens": "length"}
    result = {
        "role": "assistant",
        "content": "".join(text_parts),
        "_finish_reason": finish_map.get(data.get("stop_reason"), data.get("stop_reason")),
        "_anthropic_content": data.get("content") or [],
    }
    if thinking_parts:
        result["reasoning_content"] = "".join(thinking_parts)
    if tool_calls:
        result["tool_calls"] = tool_calls
    if data.get("usage"):
        result["_usage"] = data["usage"]
    return result


def _usage_metrics(usage: dict | None) -> dict:
    usage = usage if isinstance(usage, dict) else {}
    prompt_details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    input_details = usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
    cache_read = int(
        usage.get("cache_read_input_tokens")
        or prompt_details.get("cached_tokens")
        or input_details.get("cached_tokens")
        or 0
    )
    cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
    cache_reported = any(key in usage for key in (
        "cache_read_input_tokens", "cache_creation_input_tokens",
    )) or "cached_tokens" in prompt_details or "cached_tokens" in input_details
    return {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "cache_reported": cache_reported,
    }


def _cache_requested(messages: list[dict]) -> bool:
    return any(isinstance(message, dict) and message.get("cache_control") for message in messages)


async def _record_usage(config: ModelConfig, usage: dict | None, cache_requested: bool) -> None:
    if not usage:
        return
    metrics = _usage_metrics(usage)
    created = metrics["cache_creation_input_tokens"]
    read = metrics["cache_read_input_tokens"]
    if created or read:
        logger.info(
            "Prompt cache usage model=%s created_tokens=%s read_tokens=%s input_tokens=%s",
            config.model_id,
            created,
            read,
            metrics["input_tokens"],
        )
    try:
        from app.database import get_db
        async with get_db() as db:
            await db.execute(
                """INSERT INTO llm_usage_events
                   (id, slot, model_id, provider, input_tokens, output_tokens,
                    cache_requested, cache_reported, cache_read_input_tokens,
                    cache_creation_input_tokens, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), config.slot, config.model_id, config.provider,
                    metrics["input_tokens"], metrics["output_tokens"],
                    int(cache_requested), int(metrics["cache_reported"]), read, created,
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()
    except Exception:
        logger.warning("LLM usage metrics could not be stored", exc_info=True)

async def call_llm(
    config: ModelConfig,
    messages: list[dict],
    stream: bool = False,
    temperature: float = 0.9,
    max_tokens: int = 1000,
    tools: list[dict] | None = None,
    extended_thinking: bool = False,
) -> str | AsyncGenerator[dict, None]:
    if _is_claude(config):
        if stream:
            return _stream_llm_dispatch(
                config, messages, temperature, max_tokens, tools, extended_thinking
            )
        try:
            msg = await _call_anthropic_once(
                config, messages, temperature, max_tokens, tools, extended_thinking
            )
            content, thinking = _extract_content_and_thinking(msg)
            return content or thinking
        except UnsupportedAnthropicProtocol:
            logger.info("Gateway has no Anthropic Messages endpoint; using Chat Completions fallback")

    headers = _openai_headers(config)
    payload = {
        "model": config.model_id,
        "messages": _openai_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
    _apply_thinking_options(config, payload, extended_thinking)

    if stream:
        return _stream_llm(config, headers, payload, _cache_requested(messages))
    else:
        return await _call_llm_once(config, headers, payload, _cache_requested(messages))

async def call_llm_with_tools(
    config: ModelConfig,
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.9,
    max_tokens: int = 1000,
    extended_thinking: bool = False,
) -> dict:
    """非流式调用，返回完整的 message 对象（含 tool_calls）。"""
    if _is_claude(config):
        try:
            return await _call_anthropic_once(
                config, messages, temperature, max_tokens, tools, extended_thinking
            )
        except UnsupportedAnthropicProtocol:
            logger.info("Gateway has no Anthropic Messages endpoint; using Chat Completions fallback")

    headers = _openai_headers(config)
    payload = {
        "model": config.model_id,
        "messages": _openai_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    _apply_thinking_options(config, payload, extended_thinking)

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15)) as client:
                resp = await client.post(f"{config.api_base}/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                await _record_usage(config, data.get("usage"), _cache_requested(messages))
                choice = data["choices"][0]
                msg = choice["message"]
                msg["_finish_reason"] = choice.get("finish_reason")
                content, thinking = _extract_content_and_thinking(msg)
                msg["content"] = content
                if thinking and not msg.get("reasoning_content"):
                    msg["reasoning_content"] = thinking
                return msg
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(1 + attempt)
                continue
            raise RuntimeError(f"LLM 调用失败：{e}")


async def _call_anthropic_once(
    config: ModelConfig,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    tools: list[dict] | None,
    extended_thinking: bool,
    retries: int = 2,
) -> dict:
    payload = _anthropic_payload(
        config,
        messages,
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        extended_thinking=extended_thinking,
    )
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15)) as client:
                resp = await client.post(
                    f"{config.api_base}/messages",
                    headers=_anthropic_headers(config),
                    json=payload,
                )
                if resp.status_code in (404, 405, 501):
                    raise UnsupportedAnthropicProtocol("Anthropic Messages endpoint is unavailable")
                resp.raise_for_status()
                data = resp.json()
                await _record_usage(config, data.get("usage"), _cache_requested(messages))
                return _anthropic_response_message(data)
        except UnsupportedAnthropicProtocol:
            raise
        except Exception as exc:
            if attempt < retries:
                await asyncio.sleep(1 + attempt)
                continue
            raise RuntimeError(f"Claude Messages 调用失败：{exc}") from exc


async def _stream_llm_dispatch(
    config: ModelConfig,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    tools: list[dict] | None,
    extended_thinking: bool,
) -> AsyncGenerator[dict, None]:
    try:
        async for chunk in _stream_anthropic(
            config, messages, temperature, max_tokens, tools, extended_thinking
        ):
            yield chunk
        return
    except UnsupportedAnthropicProtocol:
        logger.info("Gateway has no Anthropic Messages endpoint; using streaming fallback")

    payload = {
        "model": config.model_id,
        "messages": _openai_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
    _apply_thinking_options(config, payload, extended_thinking)
    async for chunk in _stream_llm(config, _openai_headers(config), payload, _cache_requested(messages)):
        yield chunk


async def _stream_anthropic(
    config: ModelConfig,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    tools: list[dict] | None,
    extended_thinking: bool,
) -> AsyncGenerator[dict, None]:
    payload = _anthropic_payload(
        config,
        messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        extended_thinking=extended_thinking,
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15)) as client:
        async with client.stream(
            "POST",
            f"{config.api_base}/messages",
            headers=_anthropic_headers(config),
            json=payload,
        ) as resp:
            if resp.status_code in (404, 405, 501):
                raise UnsupportedAnthropicProtocol("Anthropic Messages endpoint is unavailable")
            resp.raise_for_status()
            accumulated_usage = {}
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    event = json_mod.loads(raw)
                except json_mod.JSONDecodeError:
                    continue
                event_type = event.get("type")
                if event_type == "message_start":
                    accumulated_usage.update((event.get("message") or {}).get("usage") or {})
                if event_type == "content_block_delta":
                    delta = event.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield {"type": "content", "content": delta["text"]}
                    elif delta.get("type") == "thinking_delta" and delta.get("thinking"):
                        yield {"type": "thinking", "content": delta["thinking"]}
                elif event_type == "message_delta":
                    accumulated_usage.update(event.get("usage") or {})
            await _record_usage(config, accumulated_usage, _cache_requested(messages))

async def _call_llm_once(
    config: ModelConfig,
    headers: dict,
    payload: dict,
    cache_requested: bool,
    retries: int = 2,
) -> str:
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15)) as client:
                resp = await client.post(f"{config.api_base}/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                await _record_usage(config, data.get("usage"), cache_requested)
                msg = data["choices"][0]["message"]
                content, thinking = _extract_content_and_thinking(msg)
                if not content and thinking:
                    content = thinking
                return content
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1 + attempt)
                continue
            raise RuntimeError(f"LLM 调用失败：{e}")

async def _stream_llm(
    config: ModelConfig,
    headers: dict,
    payload: dict,
    cache_requested: bool,
    retries: int = 2,
) -> AsyncGenerator[dict, None]:
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15)) as client:
                async with client.stream("POST", f"{config.api_base}/chat/completions", headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    usage = None
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json_mod.loads(data)
                            if isinstance(chunk.get("usage"), dict):
                                usage = chunk["usage"]
                            delta = chunk["choices"][0]["delta"]
                            content, extracted_thinking = _extract_content_and_thinking(delta)
                            if extracted_thinking:
                                yield {"type": "thinking", "content": extracted_thinking}
                            if content:
                                yield {"type": "content", "content": content}
                        except Exception:
                            continue
                    await _record_usage(config, usage, cache_requested)
                    return
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1 + attempt)
                continue
            raise RuntimeError(f"LLM 流式调用失败：{e}")


async def get_embedding(api_base: str, api_key: str, model_id: str, text: str) -> list[float] | None:
    if not all([api_base, api_key, model_id]):
        return None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "input": text,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
            resp = await client.post(f"{api_base}/embeddings", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except Exception:
        return None


async def get_embeddings_batch(api_base: str, api_key: str, model_id: str, texts: list[str]) -> list[list[float] | None]:
    if not all([api_base, api_key, model_id]):
        return [None] * len(texts)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "input": texts,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
            resp = await client.post(f"{api_base}/embeddings", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            items = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in items]
    except Exception:
        return [None] * len(texts)


def _apply_thinking_options(config: ModelConfig, payload: dict, enabled: bool) -> None:
    if not enabled:
        return
    api_base = (config.api_base or "").lower()
    model_id = (config.model_id or "").lower()
    if "gemini" not in model_id and "generativelanguage.googleapis.com" not in api_base:
        return
    payload["reasoning_effort"] = "high"
    extra_body = payload.setdefault("extra_body", {})
    google = extra_body.setdefault("google", {})
    thinking_config = google.setdefault("thinking_config", {})
    thinking_config["include_thoughts"] = True


def _extract_content_and_thinking(message: dict) -> tuple[str, str]:
    content = message.get("content") or ""
    thinking = (
        message.get("reasoning_content")
        or message.get("reasoning")
        or message.get("thinking")
        or ""
    )
    if isinstance(content, str):
        return content, str(thinking or "")
    if not isinstance(content, list):
        return "", str(thinking or "")

    content_parts = []
    thinking_parts = []
    for part in content:
        if not isinstance(part, dict):
            continue
        text = part.get("text") or part.get("content") or ""
        if not text:
            continue
        if part.get("thought") or part.get("type") in ("thinking", "reasoning"):
            thinking_parts.append(text)
        else:
            content_parts.append(text)
    if thinking:
        thinking_parts.insert(0, str(thinking))
    return "".join(content_parts), "".join(thinking_parts)
