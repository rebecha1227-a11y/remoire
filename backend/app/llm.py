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

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(f"{config.api_base}/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]
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
                content = msg.get("content") or ""
                if not content and msg.get("reasoning_content"):
                    content = msg["reasoning_content"]
                return content
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1 + attempt)
                continue
            raise RuntimeError(f"LLM 调用失败：{e}")

async def _stream_llm(api_base: str, headers: dict, payload: dict, retries: int = 2) -> AsyncGenerator[str, None]:
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
                            reasoning = delta.get("reasoning_content", "")
                            if reasoning:
                                yield {"type": "thinking", "content": reasoning}
                            content = delta.get("content", "")
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
