from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from typing import Literal
from app.auth import verify_token
from app.services import note_service

router = APIRouter(prefix="/api/note", tags=["note"])


@router.get("/unread")
async def get_unread(_=Depends(verify_token)):
    note = await note_service.get_unread()
    return {"ok": True, "data": {"note": note}}


class ReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["dismiss", "keep"] = "dismiss"


@router.post("/{note_id}/read")
async def mark_read(note_id: str, req: ReadRequest, _=Depends(verify_token)):
    try:
        await note_service.mark_read(note_id, req.action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.get("")
async def list_notes(
    kept_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1, le=10000),
    _=Depends(verify_token),
):
    offset = (page - 1) * limit
    notes = await note_service.list_notes(kept_only=kept_only, limit=limit, offset=offset)
    return {"ok": True, "data": {"notes": notes}}
