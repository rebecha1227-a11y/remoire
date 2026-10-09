import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.auth import verify_token
from app import config
from app.services import imessage_service

router = APIRouter(tags=["imessage"])


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    project_id: str | None = Field(default=None, max_length=200)
    project_secret: str | None = Field(default=None, max_length=500)
    owner_phone: str | None = Field(default=None, max_length=32)
    merge_wait_seconds: int | None = Field(default=None, ge=2, le=10)
    typing_ms_per_char: int | None = Field(default=None, ge=20, le=200)
    failure_phrase_enabled: bool | None = None


class InboundBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_id: str = Field(min_length=1, max_length=200)
    sender: str = Field(default="", max_length=64)
    text: str = Field(default="", max_length=8000)
    sent_at: str = Field(default="", max_length=64)
    chat_guid: str = Field(default="", max_length=300)


class StatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(min_length=1, max_length=32)
    detail: str = Field(default="", max_length=300)
    chat_guid: str = Field(default="", max_length=300)
    line_phone: str = Field(default="", max_length=32)


class AckBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


def verify_bridge(request: Request) -> None:
    expected = config.IMESSAGE_BRIDGE_TOKEN or ""
    provided = request.headers.get("x-remoire-bridge", "")
    if not expected or not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="桥接未授权")


@router.get("/api/settings/imessage")
async def read_imessage_settings(_=Depends(verify_token)):
    account = await imessage_service.get_account()
    return {"ok": True, "data": imessage_service.public_account(account)}


@router.put("/api/settings/imessage")
async def write_imessage_settings(body: AccountUpdate, _=Depends(verify_token)):
    fields = body.model_dump(exclude_unset=True)
    if "project_secret" in fields and not fields["project_secret"]:
        fields.pop("project_secret")
    data = await imessage_service.save_account(fields)
    return {"ok": True, "data": data}


@router.post("/api/settings/imessage/enroll")
async def enroll_imessage(_=Depends(verify_token)):
    try:
        data = await imessage_service.enroll_line()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "data": data}


@router.get("/api/internal/imessage/runtime")
async def bridge_runtime(_=Depends(verify_bridge)):
    account = await imessage_service.get_account(include_secret=True)
    return {
        "ok": True,
        "data": {
            "enabled": bool(account.get("enabled")),
            "project_id": account.get("project_id") or "",
            "project_secret": account.get("project_secret") or "",
            "owner_phone": account.get("owner_phone") or "",
            "line_phone": account.get("line_phone") or "",
            "chat_guid": account.get("chat_guid") or "",
            "merge_wait_seconds": account.get("merge_wait_seconds") or 4,
            "typing_ms_per_char": account.get("typing_ms_per_char") or 45,
        },
    }


@router.post("/api/internal/imessage/inbound")
async def bridge_inbound(body: InboundBody, _=Depends(verify_bridge)):
    result = await imessage_service.accept_inbound(
        external_id=body.external_id,
        sender=body.sender,
        text=body.text,
        sent_at=body.sent_at,
        chat_guid=body.chat_guid,
    )
    return {"ok": True, "data": result}


@router.post("/api/internal/imessage/status")
async def bridge_status(body: StatusBody, _=Depends(verify_bridge)):
    await imessage_service.set_status(body.status, body.detail, chat_guid=body.chat_guid, line_phone=body.line_phone)
    return {"ok": True}


@router.get("/api/internal/imessage/outbox")
async def bridge_outbox(_=Depends(verify_bridge)):
    actions = await imessage_service.pending_actions()
    return {"ok": True, "data": {"actions": actions}}


@router.post("/api/internal/imessage/outbox/{action_id}")
async def bridge_ack(action_id: str, body: AckBody, _=Depends(verify_bridge)):
    await imessage_service.ack_action(action_id, body.ok)
    return {"ok": True}
