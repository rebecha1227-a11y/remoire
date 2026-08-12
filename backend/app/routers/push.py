from fastapi import APIRouter, Depends
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator
from app.auth import verify_token
from app.config import VAPID_PUBLIC_KEY
from app.services import push_service

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    endpoint: AnyHttpUrl
    p256dh: str = Field(min_length=1, max_length=256)
    auth: str = Field(min_length=1, max_length=256)
    user_agent: str = Field(default="", max_length=500)
    display_name: str = Field(default="Connie", min_length=1, max_length=100)

    @field_validator("endpoint")
    @classmethod
    def require_https_endpoint(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("推送订阅地址必须使用 HTTPS")
        return value


@router.get("/vapid-public-key")
async def get_vapid_key(_=Depends(verify_token)):
    return {"ok": True, "data": {"key": VAPID_PUBLIC_KEY}}


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest, _=Depends(verify_token)):
    sub_id = await push_service.save_subscription(
        endpoint=str(req.endpoint), p256dh=req.p256dh, auth=req.auth,
        user_agent=req.user_agent, display_name=req.display_name,
    )
    return {"ok": True, "data": {"id": sub_id}}


@router.post("/unsubscribe")
async def unsubscribe(req: SubscribeRequest, _=Depends(verify_token)):
    await push_service.remove_subscription(str(req.endpoint))
    return {"ok": True}


class UpdateNameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=100)


@router.post("/update-name")
async def update_push_name(req: UpdateNameRequest, _=Depends(verify_token)):
    await push_service.update_display_name(req.display_name)
    return {"ok": True}


class PresenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool


@router.post("/presence")
async def presence(
    req: PresenceRequest,
    _=Depends(verify_token),
):
    push_service.set_presence(req.active)
    return {"ok": True}


@router.post("/test")
async def test_push(_=Depends(verify_token)):
    count = await push_service.send_push(
        title="Connie",
        body="推送测试成功 💌",
        tag="test",
        skip_if_active=False,
    )
    return {"ok": True, "data": {"sent": count}}
