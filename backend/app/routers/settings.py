from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime, timezone, timedelta

from app.auth import verify_token
from app.database import get_db
from app.services import model_settings_service
import json
import logging


router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)


class PresetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nickname: str = Field(min_length=1, max_length=100)
    provider: str | None = Field(default="openai-compatible", max_length=100)
    api_key: str = Field(min_length=1, max_length=4096)
    base_url: str = Field(min_length=1, max_length=2048)
    model_name: str = Field(min_length=1, max_length=256)


class PresetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nickname: str | None = Field(default=None, min_length=1, max_length=100)
    provider: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    model_name: str | None = Field(default=None, min_length=1, max_length=256)


class SlotUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset_id: str | None = Field(default=None, max_length=100)
    extended_thinking: bool | None = None


class ModelProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    api_key: str = Field(min_length=1, max_length=4096)
    base_url: str = Field(min_length=1, max_length=2048)
    model_name: str | None = Field(default=None, min_length=1, max_length=256)


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
    except Exception:
        logger.exception("saved model list request failed preset_id=%s", preset_id)
        raise HTTPException(status_code=502, detail="拉取模型列表失败，请检查接口地址和密钥")


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
    except Exception:
        logger.exception("draft model list request failed")
        raise HTTPException(status_code=502, detail="拉取模型列表失败，请检查接口地址和密钥")


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
    except Exception:
        logger.exception("draft model probe failed")
        raise HTTPException(status_code=502, detail="模型检测失败，请检查接口地址、密钥和模型名称")


@router.post("/model-presets/{preset_id}/test")
async def test_saved_model_config(preset_id: str, _=Depends(verify_token)):
    try:
        result = await model_settings_service.test_saved_model_config(preset_id)
        return {"ok": True, "data": result}
    except model_settings_service.PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except model_settings_service.UnsafeBaseUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("saved model probe failed preset_id=%s", preset_id)
        raise HTTPException(status_code=502, detail="模型检测失败，请检查接口地址、密钥和模型名称")


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
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    start_hour: int | None = Field(default=None, ge=0, le=23)
    end_hour: int | None = Field(default=None, ge=0, le=23)
    allow_night: bool | None = None
    max_daily: int | None = Field(default=None, ge=1, le=20)
    cooldown_minutes: int | None = Field(default=None, ge=5, le=1440)
    max_burst: int | None = Field(default=None, ge=1, le=20)
    max_rounds: int | None = Field(default=None, ge=1, le=10)
    round_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    end_on_reply: bool | None = None
    types_json: str | None = Field(default=None, max_length=500)

    @field_validator("types_json")
    @classmethod
    def validate_types_json(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("消息类型配置不是有效 JSON") from exc
        allowed = {"care", "reminder", "followup", "special"}
        if not isinstance(parsed, dict) or set(parsed) - allowed or any(type(item) is not bool for item in parsed.values()):
            raise ValueError("消息类型配置包含无效字段")
        return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


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
    allowed_columns = {
        "enabled", "start_hour", "end_hour", "allow_night", "max_daily",
        "cooldown_minutes", "max_burst", "max_rounds", "round_interval_minutes",
        "end_on_reply", "types_json",
    }
    for key in fields:
        if key not in allowed_columns:
            raise HTTPException(status_code=400, detail="主动消息设置包含未知字段")
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
            # Column identifiers come only from allowed_columns; all values stay bound.
            f"UPDATE proactive_message_settings SET {', '.join(sets)} WHERE id = ?",  # nosec B608
            tuple(params),
        )
        await db.commit()
    return {"ok": True}
