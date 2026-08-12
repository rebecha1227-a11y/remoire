from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal
from collections import defaultdict, deque
import time
from app.auth import verify_token
from app.services import diary_service
from app.services import diary_interaction_service

router = APIRouter(prefix="/api/diary", tags=["diary"])
_pin_failures: dict[str, deque[float]] = defaultdict(deque)
_PIN_WINDOW_SECONDS = 15 * 60
_PIN_MAX_FAILURES = 5


def _public_diary(diary: dict, *, redact_locked: bool = True) -> dict:
    public = dict(diary)
    public.pop("pin", None)
    public.pop("pin_hash", None)
    if redact_locked and public.get("locked"):
        public["content"] = ""
    return public


def _pin_is_rate_limited(diary_id: str) -> bool:
    now = time.monotonic()
    failures = _pin_failures[diary_id]
    while failures and now - failures[0] > _PIN_WINDOW_SECONDS:
        failures.popleft()
    return len(failures) >= _PIN_MAX_FAILURES


class DiaryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(default="无题", min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=50000)
    author: Literal["jinger"] = "jinger"
    locked: bool = False
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")

    @model_validator(mode="after")
    def require_pin_when_locked(self):
        if self.locked and not self.pin:
            raise ValueError("上锁日记必须设置四位密码")
        if not self.locked:
            self.pin = None
        return self


class InteractionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    actor: Literal["jinger"] = "jinger"
    type: Literal["comment", "unlock_request"] = "comment"
    content: str = Field(min_length=1, max_length=5000)


class DiaryLockUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    locked: bool
    pin: str = Field(pattern=r"^\d{4}$")
    actor: Literal["jinger"] = "jinger"


class PinVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    pin: str = Field(pattern=r"^\d{4}$")


@router.get("")
async def get_diaries(
    author: Literal["jinger", "connie"] = Query("connie"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100000),
    _=Depends(verify_token),
):
    diaries = await diary_service.list_diaries(
        author=author,
        limit=limit,
        offset=offset,
        include_locked_content=False,
    )
    for entry in diaries:
        entry["interactions"] = await diary_interaction_service.list_interactions(entry["id"])
    return {"ok": True, "data": diaries}


@router.post("/{diary_id}/verify-pin")
async def verify_diary_pin(diary_id: str, body: PinVerifyRequest, _=Depends(verify_token)):
    diary = await diary_interaction_service.get_diary(diary_id)
    if not diary or diary.get("author") != "jinger":
        raise HTTPException(status_code=404, detail="日记不存在")
    if not diary.get("locked"):
        return {"ok": True, "data": _public_diary(diary, redact_locked=False)}
    if _pin_is_rate_limited(diary_id):
        raise HTTPException(status_code=429, detail="密码尝试次数过多，请稍后再试")
    verified = await diary_interaction_service.verify_diary_pin(diary_id, body.pin)
    if not verified:
        _pin_failures[diary_id].append(time.monotonic())
        remaining = max(0, _PIN_MAX_FAILURES - len(_pin_failures[diary_id]))
        raise HTTPException(status_code=403, detail=f"密码不正确，还可尝试 {remaining} 次")
    _pin_failures.pop(diary_id, None)
    return {"ok": True, "data": _public_diary(verified, redact_locked=False)}


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
async def process_unlock_decisions(limit: int = Query(3, ge=1, le=20), _=Depends(verify_token)):
    decisions = await diary_interaction_service.decide_unlock_requests(limit=limit)
    return {"ok": True, "data": decisions}


@router.get("/activities")
async def get_diary_activities(limit: int = Query(30, ge=1, le=200), _=Depends(verify_token)):
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
    existing = await diary_interaction_service.get_diary(diary_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Diary not found")
    if existing.get("author") != "jinger":
        raise HTTPException(status_code=403, detail="不能修改 Connie 的日记锁")
    if existing.get("locked") and not body.locked:
        if _pin_is_rate_limited(diary_id):
            raise HTTPException(status_code=429, detail="密码尝试次数过多，请稍后再试")
        verified = await diary_interaction_service.verify_diary_pin(diary_id, body.pin)
        if not verified:
            _pin_failures[diary_id].append(time.monotonic())
            raise HTTPException(status_code=403, detail="密码不正确，无法解除日记锁")
        _pin_failures.pop(diary_id, None)
    diary = await diary_interaction_service.set_diary_lock(
        diary_id=diary_id,
        locked=body.locked,
        pin=body.pin,
        actor=body.actor,
    )
    if not diary:
        raise HTTPException(status_code=404, detail="Diary not found")
    return {"ok": True, "data": _public_diary(diary)}


@router.delete("/{diary_id}/interactions/{interaction_id}")
async def delete_diary_interaction(diary_id: str, interaction_id: str, _=Depends(verify_token)):
    deleted = await diary_interaction_service.delete_interaction(
        interaction_id,
        diary_id=diary_id,
        actor="jinger",
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Interaction not found")
    items = await diary_interaction_service.list_interactions(diary_id)
    return {"ok": True, "data": {"items": items}}
