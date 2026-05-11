import httpx
import json as json_mod
import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator

@dataclass
class ModelConfig:
    api_base: str
    api_key: str
    model_id: str

async def call_llm(
    config: ModelConfig,
    messages: list[dict],
    stream: bool = False,
    temperature: float = 0.9,
    max_tokens: int = 1000,
    tools: list[dict] | None = None,
    extended_thinking: bool = False,
) -> str | AsyncGenerator[dict, None]:
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
    _apply_thinking_options(config, payload, extended_thinking)

    if stream:
        return _stream_llm(config.api_base, headers, payload)
    else:
        return await _call_llm_once(config.api_base, headers, payload)

async def call_llm_with_tools(
    config: ModelConfig,
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.9,
    max_tokens: int = 1000,
    extended_thinking: bool = False,
) -> dict:
    """非流式调用，返回完整的 message 对象（含 tool_calls）。"""
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    _apply_thinking_options(config, payload, extended_thinking)

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(f"{config.api_base}/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                choice = resp.json()["choices"][0]
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

async def _call_llm_once(api_base: str, headers: dict, payload: dict, retries: int = 2) -> str:
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
                content, thinking = _extract_content_and_thinking(msg)
                if not content and thinking:
                    content = thinking
                return content
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1 + attempt)
                continue
            raise RuntimeError(f"LLM 调用失败：{e}")

async def _stream_llm(api_base: str, headers: dict, payload: dict, retries: int = 2) -> AsyncGenerator[dict, None]:
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream("POST", f"{api_base}/chat/completions", headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json_mod.loads(data)
                            delta = chunk["choices"][0]["delta"]
                            content, extracted_thinking = _extract_content_and_thinking(delta)
                            if extracted_thinking:
                                yield {"type": "thinking", "content": extracted_thinking}
                            if content:
                                yield {"type": "content", "content": content}
                        except Exception:
                            continue
                    return
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1 + attempt)
                continue
            raise RuntimeError(f"LLM 流式调用失败：{e}")


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
