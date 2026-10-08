from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.auth import verify_token
from app.services import prompt_profile_service as profiles


def private_response(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/settings/prompt-profiles", tags=["settings"],
                   dependencies=[Depends(verify_token), Depends(private_response)])


def check_editable(key: str):
    if key not in ("identity", "voice", "scene"):
        raise HTTPException(404, "配置不存在")


class SaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(max_length=profiles.MAX_CONTENT)
    enabled: bool = False
    expected_version: int = Field(ge=1)


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    expected_version: int = Field(ge=1)


async def result(operation):
    try:
        return {"ok": True, "data": await operation}
    except KeyError:
        raise HTTPException(404, "配置或版本不存在")
    except profiles.ProfileConflict as exc:
        raise HTTPException(409, str(exc))


@router.get("")
async def list_profiles():
    return {"ok": True, "data": [item for item in await profiles.list_profiles() if item["key"] != "original"]}


@router.get("/preview")
async def preview(scene: bool = False):
    # Assembles saved configuration only; never calls a model or diary decisions.
    return {"ok": True, "data": {"content": await profiles.load_shared(scene=scene)}}


@router.put("/{key}")
async def save(key: str, req: SaveRequest):
    check_editable(key)
    return await result(profiles.save_profile(key, req.content, req.enabled, req.expected_version))


@router.get("/{key}/versions")
async def versions(key: str, before: int | None = Query(default=None, ge=1)):
    check_editable(key)
    return await result(profiles.list_versions(key, before))


@router.get("/{key}/versions/{version}")
async def version(key: str, version: int):
    check_editable(key)
    return await result(profiles.get_version(key, version))


@router.post("/{key}/restore")
async def restore(key: str, req: RestoreRequest):
    check_editable(key)
    return await result(profiles.restore_version(key, req.version, req.expected_version))
