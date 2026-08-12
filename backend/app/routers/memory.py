from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from app.auth import verify_token
from app.services import memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])
Tag = Annotated[str, Field(min_length=1, max_length=100)]


class AcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    memory_type: Literal["fact", "event", "unresolved", "date", "consciousness"] | None = None
    tags: list[Tag] | None = Field(default=None, max_length=20)
    layer: Literal["core", "long", "short", "consciousness"] | None = None
    event_date: date | None = None


class UpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    tags: list[Tag] | None = Field(default=None, max_length=20)
    layer: Literal["core", "long", "short", "consciousness"] | None = None
    memory_type: Literal["fact", "event", "unresolved", "date", "consciousness"] | None = None
    event_date: date | None = None
    event_time: str | None = Field(default=None, max_length=32)
    valence: float | None = Field(default=None, ge=0.0, le=1.0)
    arousal: float | None = Field(default=None, ge=0.0, le=1.0)
    unresolved: bool | None = None
    pinned: bool | None = None


class MoveLayerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_layer: Literal["core", "long", "short", "consciousness"]


class RecallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=2000)
    tags: list[Tag] = Field(default_factory=list, max_length=20)
    layer: Literal["core", "long", "short", "consciousness"] = "long"
    memory_type: Literal["fact", "event", "unresolved", "date", "consciousness"] = "fact"
    event_date: date | None = None
    event_time: str | None = Field(default=None, max_length=32)
    valence: float = Field(default=0.0, ge=0.0, le=1.0)
    arousal: float = Field(default=0.0, ge=0.0, le=1.0)
    unresolved: bool = False


# ── 候选 ──

@router.get("/candidates")
async def get_candidates(
    status: Literal["pending", "accepted", "rejected"] = Query("pending"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    _=Depends(verify_token),
):
    candidates = await memory_service.list_candidates(status=status, limit=limit, offset=offset)
    return {"ok": True, "data": candidates}


@router.post("/candidates/{candidate_id}/accept")
async def accept_candidate(candidate_id: str, req: AcceptRequest = None, _=Depends(verify_token)):
    try:
        result = await memory_service.accept_candidate(
            candidate_id,
            content=req.content if req else None,
            memory_type=req.memory_type if req else None,
            tags=req.tags if req else None,
            layer=req.layer if req else None,
            event_date=req.event_date.isoformat() if req and req.event_date else None,
        )
        return {"ok": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/candidates/{candidate_id}/reject")
async def reject_candidate(candidate_id: str, _=Depends(verify_token)):
    try:
        await memory_service.reject_candidate(candidate_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── 统计 ──

@router.get("/stats")
async def get_stats(_=Depends(verify_token)):
    stats = await memory_service.get_layer_stats()
    return {"ok": True, "data": stats}


@router.get("/heatmap")
async def get_heatmap(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    _=Depends(verify_token),
):
    data = await memory_service.get_heatmap(year, month)
    return {"ok": True, "data": data}


# ── 正式记忆 ──

@router.post("")
async def create_memory(req: CreateRequest, _=Depends(verify_token)):
    result = await memory_service.create_memory(
        content=req.content,
        tags=req.tags,
        layer=req.layer,
        memory_type=req.memory_type,
        event_date=req.event_date.isoformat() if req.event_date else None,
        event_time=req.event_time,
        valence=req.valence,
        arousal=req.arousal,
        unresolved=req.unresolved,
    )
    if result["memory"].get("duplicate"):
        raise HTTPException(status_code=409, detail="相同内容的记忆已经存在")
    return {"ok": True, "data": result}

@router.get("")
async def get_memories(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100000),
    search: str | None = Query(None, max_length=200),
    layer: Literal["core", "long", "short", "consciousness"] | None = Query(None),
    memory_type: Literal["fact", "event", "unresolved", "date", "consciousness"] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    sort_by: Literal["created_at", "weight"] = Query("created_at"),
    _=Depends(verify_token),
):
    result = await memory_service.list_memories(
        limit=limit, offset=offset, search=search,
        layer=layer, memory_type=memory_type,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        sort_by=sort_by,
    )
    return {"ok": True, "data": result}


@router.get("/{memory_id}")
async def get_memory(memory_id: str, _=Depends(verify_token)):
    memory = await memory_service.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"ok": True, "data": memory}


@router.get("/{memory_id}/related")
async def get_related_memories(memory_id: str, limit: int = Query(6, ge=1, le=20), _=Depends(verify_token)):
    if not await memory_service.get_memory(memory_id):
        raise HTTPException(status_code=404, detail="记忆不存在")
    related = await memory_service.get_related_memories(memory_id, limit=limit)
    return {"ok": True, "data": related}


@router.put("/{memory_id}")
async def update_memory(memory_id: str, req: UpdateRequest, _=Depends(verify_token)):
    try:
        fields = req.model_fields_set
        kwargs = {}
        if "content" in fields:
            kwargs["content"] = req.content
        if "tags" in fields:
            kwargs["tags"] = req.tags
        if "layer" in fields:
            kwargs["layer"] = req.layer
        if "memory_type" in fields:
            kwargs["memory_type"] = req.memory_type
        if "event_date" in fields:
            kwargs["event_date"] = req.event_date.isoformat() if req.event_date else None
        else:
            kwargs["event_date"] = ...
        if "event_time" in fields:
            kwargs["event_time"] = req.event_time
        else:
            kwargs["event_time"] = ...
        if "valence" in fields:
            kwargs["valence"] = req.valence
        if "arousal" in fields:
            kwargs["arousal"] = req.arousal
        if "unresolved" in fields:
            kwargs["unresolved"] = req.unresolved
        if "pinned" in fields:
            kwargs["pinned"] = req.pinned
        result = await memory_service.update_memory(memory_id, **kwargs)
        return {"ok": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{memory_id}/move")
async def move_memory_layer(memory_id: str, req: MoveLayerRequest, _=Depends(verify_token)):
    try:
        result = await memory_service.move_layer(memory_id, req.target_layer)
        return {"ok": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{memory_id}/resolve")
async def resolve_memory(memory_id: str, _=Depends(verify_token)):
    try:
        result = await memory_service.resolve_memory(memory_id)
        return {"ok": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, _=Depends(verify_token)):
    try:
        await memory_service.delete_memory(memory_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── 召回 ──

@router.post("/recall")
async def recall_memories(req: RecallRequest, _=Depends(verify_token)):
    memories = await memory_service.recall(query=req.query, limit=req.limit)
    return {"ok": True, "data": memories}


@router.post("/backfill-embeddings")
async def backfill_embeddings(_=Depends(verify_token)):
    count = await memory_service.backfill_embeddings()
    return {"ok": True, "data": {"count": count}}


@router.post("/digest")
async def run_digest(_=Depends(verify_token)):
    count = await memory_service.run_digest()
    return {"ok": True, "data": {"deleted": count}}


@router.post("/backfill-emotions")
async def backfill_emotions(_=Depends(verify_token)):
    count = await memory_service.backfill_emotions()
    return {"ok": True, "data": {"count": count}}
