from typing import Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.auth import verify_token
from app.services.chat_service import get_or_create_conversation, get_history, search_messages, stream_chat, debug_prompt
from app.services.image_storage import MAX_ENCODED_IMAGE_CHARS, decode_image
import json
import asyncio
from contextlib import suppress

router = APIRouter(prefix="/api/chat", tags=["chat"])

class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=20_000)
    conversation_id: str | None = Field(default=None, max_length=64)
    image: str | None = Field(default=None, max_length=MAX_ENCODED_IMAGE_CHARS)
    sticker_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    mode: Literal["daily", "deep"] = "daily"
    reply_style: Literal["split", "whole"] = "split"

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str | None) -> str | None:
        if value:
            decode_image(value)
        return value

@router.post("/send")
async def send_message(req: SendRequest, _=Depends(verify_token)):
    image, message, image_kind = req.image, req.message, "photo"
    if req.sticker_id:
        if req.image:
            raise HTTPException(400, "不能同时发送照片和表情包")
        from app.services.sticker_service import get_media
        import base64
        try:
            raw, mime, label = await get_media(req.sticker_id)
        except ValueError:
            raise HTTPException(404, "表情包不存在")
        except Exception:
            raise HTTPException(502, "表情包暂时无法读取，请稍后重试")
        image = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
        message, image_kind = f"[表情包：{label}]", "sticker"
    conversation_id = await get_or_create_conversation(req.conversation_id)

    async def event_stream():
        yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conversation_id})}\n\n"
        try:
            source = stream_chat(conversation_id, message, image=image, user_image_kind=image_kind, mode=req.mode or "daily", reply_style=req.reply_style or "split")
            async for item in _with_heartbeat(source):
                if item is None:
                    yield ": keepalive\n\n"
                else:
                    event = item if isinstance(item, dict) else {"type": "chunk", "content": item}
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            from app.llm import public_model_error
            code, detail = public_model_error(exc)
            yield f"data: {json.dumps({'type': 'error', 'code': code, 'content': detail})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.post("/debug")
async def debug_system_prompt(req: SendRequest, _=Depends(verify_token)):
    conversation_id = await get_or_create_conversation(req.conversation_id)
    result = await debug_prompt(conversation_id, req.message)
    return {"ok": True, "data": result}

@router.get("/latest")
async def latest_conversation(_=Depends(verify_token)):
    from app.database import get_db
    async with get_db() as db:
        async with db.execute("SELECT id FROM conversations ORDER BY updated_at DESC LIMIT 1") as cur:
            row = await cur.fetchone()
    if not row:
        return {"ok": True, "data": None}
    return {"ok": True, "data": {"conversation_id": row["id"]}}

@router.get("/history")
async def chat_history(
    conversation_id: str = Query(max_length=64),
    limit: int = Query(50, ge=1, le=200),
    _=Depends(verify_token),
):
    messages = await get_history(conversation_id, limit=limit)
    from app.services.imessage_interactions import enrich_history
    messages = await enrich_history(messages)
    return {"ok": True, "data": {"messages": messages, "conversation_id": conversation_id}}

@router.get("/search")
async def chat_search(
    conversation_id: str = Query(max_length=64),
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(80, ge=1, le=200),
    _=Depends(verify_token),
):
    messages = await search_messages(conversation_id, q, limit=limit)
    return {"ok": True, "data": {"messages": messages, "conversation_id": conversation_id}}

@router.get("/image/{message_id}")
async def chat_image(message_id: str, _=Depends(verify_token)):
    from app.services.chat_service import get_message_image
    from fastapi import HTTPException
    from fastapi.responses import Response
    result = await get_message_image(message_id)
    if not result:
        raise HTTPException(status_code=404, detail="not found")
    raw_bytes, mime = result
    return Response(content=raw_bytes, media_type=mime)


async def _with_heartbeat(source, interval=15):
    """Keep proxies alive during generation without cancelling the pending call."""
    pending = None
    try:
        while True:
            pending = asyncio.create_task(anext(source))
            while not (await asyncio.wait({pending}, timeout=interval))[0]:
                yield None
            finished, pending = pending, None
            try:
                item = finished.result()
            except StopAsyncIteration:
                break
            yield item
    finally:
        if pending is not None:
            pending.cancel()
            with suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending
        await source.aclose()


@router.get("/stickers")
async def sticker_catalogue(q: str = Query('', max_length=100), category: str = Query('', max_length=100), offset: int = Query(0, ge=0), limit: int = Query(24, ge=1, le=48), _=Depends(verify_token)):
    from app.services.sticker_service import list_catalogue
    return {"ok": True, "data": await list_catalogue(q, category, offset, limit)}


@router.get("/stickers/{sticker_id}/image")
async def sticker_image(sticker_id: str, _=Depends(verify_token)):
    from app.services.sticker_service import get_media
    from fastapi.responses import Response
    try:
        raw, mime, _ = await get_media(sticker_id)
    except ValueError:
        raise HTTPException(404, "表情包不存在")
    except Exception:
        raise HTTPException(502, "表情包暂时无法读取")
    return Response(raw, media_type=mime, headers={"Cache-Control": "private, no-store"})
