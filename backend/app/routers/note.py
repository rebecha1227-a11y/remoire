from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import verify_token
from app.services import note_service

router = APIRouter(prefix="/api/note", tags=["note"])


@router.get("/unread")
async def get_unread(_=Depends(verify_token)):
    note = await note_service.get_unread()
    return {"ok": True, "data": {"note": note}}


class ReadRequest(BaseModel):
    action: str = "dismiss"


@router.post("/{note_id}/read")
async def mark_read(note_id: str, req: ReadRequest, _=Depends(verify_token)):
    await note_service.mark_read(note_id, req.action)
    return {"ok": True}


@router.get("")
async def list_notes(kept_only: bool = False, limit: int = 20, page: int = 1, _=Depends(verify_token)):
    offset = (page - 1) * limit
    notes = await note_service.list_notes(kept_only=kept_only, limit=limit, offset=offset)
    return {"ok": True, "data": {"notes": notes}}
