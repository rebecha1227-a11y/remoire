from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from app.auth import verify_token
from app.database import get_db
from app.services import model_settings_service


router = APIRouter(prefix="/api/settings", tags=["settings"])


class PresetCreateRequest(BaseModel):
    nickname: str
    provider: str | None = "openai-compatible"
    api_key: str
    base_url: str
    model_name: str


class PresetUpdateRequest(BaseModel):
    nickname: str | None = None
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model_name: str | None = None


class SlotUpdateRequest(BaseModel):
    preset_id: str | None = None
    extended_thinking: bool | None = None


class ModelProbeRequest(BaseModel):
    api_key: str
    base_url: str
    model_name: str | None = None


@router.get("/model-presets")
async def list_model_presets(_=Depends(verify_token)):
    presets = await model_settings_service.list_presets()
    return {"ok": True, "data": presets}


@router.post("/model-presets")
async def create_model_preset(req: PresetCreateRequest, _=Depends(verify_token)):
    preset = await model_settings_service.create_preset(req.model_dump())
    return {"ok": True, "data": preset}


@router.put("/model-presets/{preset_id}")
async def update_model_preset(preset_id: str, req: PresetUpdateRequest, _=Depends(verify_token)):
    try:
        preset = await model_settings_service.update_preset(
            preset_id,
            req.model_dump(exclude_unset=True),
        )
        return {"ok": True, "data": preset}
    except model_settings_service.PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/model-presets/{preset_id}")
async def delete_model_preset(preset_id: str, _=Depends(verify_token)):
    try:
        await model_settings_service.delete_preset(preset_id)
        return {"ok": True}
    except model_settings_service.PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/model-presets/{preset_id}/models")
async def list_models_for_preset(preset_id: str, _=Depends(verify_token)):
    try:
        models = await model_settings_service.list_remote_models(preset_id)
        return {"ok": True, "data": models}
    except model_settings_service.PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except model_settings_service.UnsafeBaseUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"拉取模型列表失败：{exc}")


@router.post("/model-presets/models")
async def list_models_for_config(req: ModelProbeRequest, _=Depends(verify_token)):
    try:
        models = await model_settings_service.list_remote_models_for_config(
            api_key=req.api_key,
            base_url=req.base_url,
        )
        return {"ok": True, "data": models}
    except model_settings_service.UnsafeBaseUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"拉取模型列表失败：{exc}")


@router.post("/model-presets/test")
async def test_model_config(req: ModelProbeRequest, _=Depends(verify_token)):
    if not req.model_name:
        raise HTTPException(status_code=400, detail="请选择模型")
    try:
        result = await model_settings_service.test_model_config(
            api_key=req.api_key,
            base_url=req.base_url,
            model_name=req.model_name,
        )
        return {"ok": True, "data": result}
    except model_settings_service.UnsafeBaseUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"模型检测失败：{exc}")


@router.post("/model-presets/{preset_id}/test")
async def test_saved_model_config(preset_id: str, _=Depends(verify_token)):
    try:
        result = await model_settings_service.test_saved_model_config(preset_id)
        return {"ok": True, "data": result}
    except model_settings_service.PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except model_settings_service.UnsafeBaseUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"模型检测失败：{exc}")


@router.get("/slots")
async def list_model_slots(_=Depends(verify_token)):
    slots = await model_settings_service.list_slots()
    return {"ok": True, "data": slots}


@router.put("/slots/{slot}")
async def update_model_slot(slot: str, req: SlotUpdateRequest, _=Depends(verify_token)):
    try:
        payload = req.model_dump(exclude_unset=True)
        updated = await model_settings_service.update_slot(slot, **payload)
        return {"ok": True, "data": updated}
    except (ValueError, model_settings_service.PresetNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 主动消息设置 ──

class ProactiveSettingsRequest(BaseModel):
    enabled: bool | None = None
    start_hour: int | None = None
    end_hour: int | None = None
    allow_night: bool | None = None
    max_daily: int | None = None
    cooldown_minutes: int | None = None
    max_burst: int | None = None
    max_rounds: int | None = None
    round_interval_minutes: int | None = None
    end_on_reply: bool | None = None
    types_json: str | None = None


BJ_TZ = timezone(timedelta(hours=8))


@router.get("/proactive")
async def get_proactive_settings(_=Depends(verify_token)):
    async with get_db() as db:
        async with db.execute("SELECT * FROM proactive_message_settings WHERE id = 1") as cur:
            row = await cur.fetchone()
    if not row:
        async with get_db() as db:
            now = datetime.now(BJ_TZ).isoformat()
            await db.execute(
                "INSERT OR IGNORE INTO proactive_message_settings (id, updated_at) VALUES (1, ?)",
                (now,),
            )
            await db.commit()
            async with db.execute("SELECT * FROM proactive_message_settings WHERE id = 1") as cur:
                row = await cur.fetchone()
    import json
    data = dict(row)
    data.pop("id", None)
    data["enabled"] = bool(data.get("enabled", 1))
    data["allow_night"] = bool(data.get("allow_night", 0))
    data["end_on_reply"] = bool(data.get("end_on_reply", 1))
    types_raw = data.pop("types_json", None)
    try:
        data["types"] = json.loads(types_raw) if types_raw else {"care": True, "reminder": True, "followup": True, "special": True}
    except (json.JSONDecodeError, TypeError):
        data["types"] = {"care": True, "reminder": True, "followup": True, "special": True}
    return {"ok": True, "data": data}


@router.put("/proactive")
async def update_proactive_settings(req: ProactiveSettingsRequest, _=Depends(verify_token)):
    fields = req.model_fields_set
    if not fields:
        return {"ok": True}
    sets = []
    params = []
    for key in fields:
        val = getattr(req, key)
        if key in ("enabled", "allow_night", "end_on_reply"):
            val = 1 if val else 0
        sets.append(f"{key} = ?")
        params.append(val)
    now = datetime.now(BJ_TZ).isoformat()
    sets.append("updated_at = ?")
    params.append(now)
    params.append(1)
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO proactive_message_settings (id, updated_at) VALUES (1, ?)",
            (now,),
        )
        await db.execute(
            f"UPDATE proactive_message_settings SET {', '.join(sets)} WHERE id = ?",
            tuple(params),
        )
        await db.commit()
    return {"ok": True}
