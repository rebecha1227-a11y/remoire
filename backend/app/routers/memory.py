from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.auth import verify_token
from app.services import memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class AcceptRequest(BaseModel):
    content: str | None = None
    memory_type: str | None = None
    tags: list[str] | None = None


class UpdateRequest(BaseModel):
    content: str | None = None
    tags: list[str] | None = None


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


# ── 正式记忆 ──

@router.get("")
async def get_memories(
    limit: int = Query(50),
    offset: int = Query(0),
    search: str | None = Query(None),
    _=Depends(verify_token),
):
    memories = await memory_service.list_memories(limit=limit, offset=offset, search=search)
    return {"ok": True, "data": memories}


@router.get("/{memory_id}")
async def get_memory(memory_id: str, _=Depends(verify_token)):
    memory = await memory_service.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"ok": True, "data": memory}


@router.put("/{memory_id}")
async def update_memory(memory_id: str, req: UpdateRequest, _=Depends(verify_token)):
    try:
        result = await memory_service.update_memory(memory_id, content=req.content, tags=req.tags)
        return {"ok": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
