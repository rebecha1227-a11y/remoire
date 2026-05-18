from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.auth import verify_token
from app.services.chat_service import get_or_create_conversation, get_history, search_messages, stream_chat, debug_prompt
import json

router = APIRouter(prefix="/api/chat", tags=["chat"])

class SendRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    image: str | None = None
    mode: str | None = "daily"
    reply_style: str | None = "split"

@router.post("/send")
async def send_message(req: SendRequest, _=Depends(verify_token)):
    conversation_id = await get_or_create_conversation(req.conversation_id)

    async def event_stream():
        yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conversation_id})}\n\n"
        had_error = False
        async for item in stream_chat(conversation_id, req.message, image=req.image, mode=req.mode or "daily", reply_style=req.reply_style or "split"):
            if isinstance(item, dict):
                yield f"data: {json.dumps(item)}\n\n"
                if item.get("type") == "error":
                    had_error = True
                    break
            else:
                yield f"data: {json.dumps({'type': 'chunk', 'content': item})}\n\n"
        if not had_error:
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
async def chat_history(conversation_id: str, limit: int = 50, _=Depends(verify_token)):
    messages = await get_history(conversation_id, limit=limit)
    return {"ok": True, "data": {"messages": messages, "conversation_id": conversation_id}}

@router.get("/search")
async def chat_search(conversation_id: str, q: str, limit: int = 80, _=Depends(verify_token)):
    messages = await search_messages(conversation_id, q, limit=limit)
    return {"ok": True, "data": {"messages": messages, "conversation_id": conversation_id}}

@router.get("/image/{message_id}")
async def chat_image(message_id: str, token: str = ""):
    from app.config import API_SECRET_KEY
    from app.services.chat_service import get_message_image
    from fastapi import HTTPException
    from fastapi.responses import Response
    if token != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="无效的 token")
    result = await get_message_image(message_id)
    if not result:
        raise HTTPException(status_code=404, detail="not found")
    raw_bytes, mime = result
    return Response(content=raw_bytes, media_type=mime)
