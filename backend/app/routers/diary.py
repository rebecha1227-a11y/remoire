from fastapi import APIRouter, Depends, Query
from app.auth import verify_token
from app.services import diary_service

router = APIRouter(prefix="/api/diary", tags=["diary"])


@router.get("")
async def get_diaries(
    author: str = Query("connie"),
    limit: int = Query(50),
    offset: int = Query(0),
    _=Depends(verify_token),
):
    diaries = await diary_service.list_diaries(author=author, limit=limit, offset=offset)
    return {"ok": True, "data": diaries}
