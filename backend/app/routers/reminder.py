from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from app.auth import verify_token
from app.services import reminder_service

router = APIRouter(prefix="/api/reminder", tags=["reminder"])


class CreateRequest(BaseModel):
    content: str
    remind_at: str
    urgent: bool = False


@router.get("")
async def get_reminders(
    status: str | None = Query("pending"),
    limit: int = Query(20),
    _=Depends(verify_token),
):
    items = await reminder_service.list_reminders(status=status, limit=limit)
    return {"ok": True, "data": {"items": items, "total": len(items)}}


@router.get("/today")
async def get_today(
    _=Depends(verify_token),
):
    items = await reminder_service.get_today_reminders()
    return {"ok": True, "data": items}


@router.get("/upcoming")
async def get_upcoming(
    days: int = Query(7),
    _=Depends(verify_token),
):
    items = await reminder_service.get_upcoming_reminders(days=days)
    return {"ok": True, "data": items}


@router.get("/date/{date_str}")
async def get_by_date(
    date_str: str,
    _=Depends(verify_token),
):
    items = await reminder_service.get_reminders_for_date(date_str)
    return {"ok": True, "data": items}


@router.post("")
async def create_reminder(
    req: CreateRequest,
    _=Depends(verify_token),
):
    result = await reminder_service.create_reminder(
        content=req.content,
        remind_at=req.remind_at,
        urgent=req.urgent,
    )
    return {"ok": True, "data": result}


@router.post("/{reminder_id}/done")
async def mark_done(
    reminder_id: str,
    _=Depends(verify_token),
):
    ok = await reminder_service.complete_reminder(reminder_id)
    return {"ok": ok}


@router.post("/{reminder_id}/dismiss")
async def dismiss(
    reminder_id: str,
    _=Depends(verify_token),
):
    ok = await reminder_service.dismiss_reminder(reminder_id)
    return {"ok": ok}
