from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.auth import verify_token
from app.services import memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class AcceptRequest(BaseModel):
    content: str | None = None
    memory_type: str | None = None
    tags: list[str] | None = None
    layer: str | None = None
    event_date: str | None = None


class UpdateRequest(BaseModel):
    content: str | None = None
    tags: list[str] | None = None
    layer: str | None = None
    memory_type: str | None = None
    event_date: str | None = None
    event_time: str | None = None
    valence: float | None = None
    arousal: float | None = None
    unresolved: bool | None = None
    pinned: bool | None = None


class MoveLayerRequest(BaseModel):
    target_layer: str


class RecallRequest(BaseModel):
    query: str
    limit: int = 5


# ── 候选 ──

@router.get("/candidates")
async def get_candidates(
    status: str = Query("pending"),
    limit: int = Query(20),
    offset: int = Query(0),
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
            event_date=req.event_date if req else None,
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
    year: int = Query(...),
    month: int = Query(...),
    _=Depends(verify_token),
):
    data = await memory_service.get_heatmap(year, month)
    return {"ok": True, "data": data}


# ── 正式记忆 ──

@router.get("")
async def get_memories(
    limit: int = Query(50),
    offset: int = Query(0),
    search: str | None = Query(None),
    layer: str | None = Query(None),
    memory_type: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    sort_by: str = Query("created_at"),
    _=Depends(verify_token),
):
    result = await memory_service.list_memories(
        limit=limit, offset=offset, search=search,
        layer=layer, memory_type=memory_type,
        date_from=date_from, date_to=date_to,
        sort_by=sort_by,
    )
    return {"ok": True, "data": result}


@router.get("/{memory_id}")
async def get_memory(memory_id: str, _=Depends(verify_token)):
    memory = await memory_service.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"ok": True, "data": memory}


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
            kwargs["event_date"] = req.event_date
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
