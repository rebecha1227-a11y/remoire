from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from app.auth import verify_token
from app.services import diary_service

router = APIRouter(prefix="/api/diary", tags=["diary"])


class DiaryCreate(BaseModel):
    title: str = "无题"
    content: str
    author: str = "jinger"
    locked: bool = False
    pin: str | None = None


@router.get("")
async def get_diaries(
    author: str = Query("connie"),
    limit: int = Query(50),
    offset: int = Query(0),
    _=Depends(verify_token),
):
    diaries = await diary_service.list_diaries(author=author, limit=limit, offset=offset)
    return {"ok": True, "data": diaries}


@router.post("")
async def create_diary(body: DiaryCreate, _=Depends(verify_token)):
    entry = await diary_service.create_diary(
        title=body.title, content=body.content, author=body.author,
        locked=body.locked, pin=body.pin
    )
    return {"ok": True, "data": entry}
