from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.auth import verify_token
from app.services import diary_service
from app.services import diary_interaction_service

router = APIRouter(prefix="/api/diary", tags=["diary"])


class DiaryCreate(BaseModel):
    title: str = "无题"
    content: str
    author: str = "jinger"
    locked: bool = False
    pin: str | None = None


class InteractionCreate(BaseModel):
    actor: str = "jinger"
    type: str = "comment"
    content: str | None = None


class DiaryLockUpdate(BaseModel):
    locked: bool
    pin: str | None = None
    actor: str = "connie"


class UnlockRespond(BaseModel):
    grant: bool
    note: str | None = None


@router.get("")
async def get_diaries(
    author: str = Query("connie"),
    limit: int = Query(50),
    offset: int = Query(0),
    _=Depends(verify_token),
):
    diaries = await diary_service.list_diaries(author=author, limit=limit, offset=offset)
    for entry in diaries:
        entry["interactions"] = await diary_interaction_service.list_interactions(entry["id"])
    return {"ok": True, "data": diaries}


@router.post("")
async def create_diary(body: DiaryCreate, _=Depends(verify_token)):
    entry = await diary_service.create_diary(
        title=body.title,
        content=body.content,
        author=body.author,
        locked=body.locked,
        pin=body.pin,
    )
    await diary_interaction_service.create_interaction(
        diary_id=entry["id"],
        actor=body.author,
        type="wrote",
        content=body.title,
    )
    return {"ok": True, "data": entry}


@router.post("/unlock-decisions")
async def process_unlock_decisions(limit: int = Query(3), _=Depends(verify_token)):
    decisions = await diary_interaction_service.decide_unlock_requests(limit=limit)
    return {"ok": True, "data": decisions}


@router.get("/activities")
async def get_diary_activities(limit: int = Query(30), _=Depends(verify_token)):
    items = await diary_interaction_service.list_recent_activities(limit=limit)
    return {"ok": True, "data": items}


@router.get("/{diary_id}/interactions")
async def get_diary_interactions(diary_id: str, _=Depends(verify_token)):
    diary = await diary_interaction_service.get_diary(diary_id)
    if not diary:
        raise HTTPException(status_code=404, detail="Diary not found")
    items = await diary_interaction_service.list_interactions(diary_id)
    return {"ok": True, "data": items}


@router.post("/{diary_id}/interactions")
async def create_diary_interaction(diary_id: str, body: InteractionCreate, _=Depends(verify_token)):
    diary = await diary_interaction_service.get_diary(diary_id)
    if not diary:
        raise HTTPException(status_code=404, detail="Diary not found")
    item = await diary_interaction_service.create_with_optional_connie_reply(
        diary_id=diary_id,
        actor=body.actor,
        type=body.type,
        content=body.content,
    )
    items = await diary_interaction_service.list_interactions(diary_id)
    return {"ok": True, "data": {"created": item, "items": items}}


@router.post("/{diary_id}/lock")
async def update_diary_lock(diary_id: str, body: DiaryLockUpdate, _=Depends(verify_token)):
    diary = await diary_interaction_service.set_diary_lock(
        diary_id=diary_id,
        locked=body.locked,
        pin=body.pin,
        actor=body.actor,
    )
    if not diary:
        raise HTTPException(status_code=404, detail="Diary not found")
    return {"ok": True, "data": diary}


@router.delete("/{diary_id}/interactions/{interaction_id}")
async def delete_diary_interaction(diary_id: str, interaction_id: str, _=Depends(verify_token)):
    deleted = await diary_interaction_service.delete_interaction(interaction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Interaction not found")
    items = await diary_interaction_service.list_interactions(diary_id)
    return {"ok": True, "data": {"items": items}}


@router.post("/{diary_id}/unlock-respond")
async def respond_diary_unlock(diary_id: str, body: UnlockRespond, _=Depends(verify_token)):
    item = await diary_interaction_service.respond_unlock(
        diary_id=diary_id,
        grant=body.grant,
        note=body.note,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Diary not found")
    diary = await diary_interaction_service.get_diary(diary_id)
    items = await diary_interaction_service.list_interactions(diary_id)
    return {"ok": True, "data": {"diary": diary, "created": item, "items": items}}
