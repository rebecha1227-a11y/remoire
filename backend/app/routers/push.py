from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import verify_token
from app.config import VAPID_PUBLIC_KEY
from app.services import push_service

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str = ""
    display_name: str = "Connie"


@router.get("/vapid-public-key")
async def get_vapid_key(_=Depends(verify_token)):
    return {"ok": True, "data": {"key": VAPID_PUBLIC_KEY}}


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest, _=Depends(verify_token)):
    sub_id = await push_service.save_subscription(
        endpoint=req.endpoint, p256dh=req.p256dh, auth=req.auth,
        user_agent=req.user_agent, display_name=req.display_name,
    )
    return {"ok": True, "data": {"id": sub_id}}


@router.post("/unsubscribe")
async def unsubscribe(req: SubscribeRequest, _=Depends(verify_token)):
    await push_service.remove_subscription(req.endpoint)
    return {"ok": True}


class UpdateNameRequest(BaseModel):
    display_name: str


@router.post("/update-name")
async def update_push_name(req: UpdateNameRequest, _=Depends(verify_token)):
    await push_service.update_display_name(req.display_name)
    return {"ok": True}


class PresenceRequest(BaseModel):
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
