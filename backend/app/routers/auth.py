import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.auth import (
    clear_login_failures,
    create_session,
    delete_session,
    login_is_rate_limited,
    record_login_failure,
    verify_password,
    verify_mcp_token,
    verify_token,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    if not config.APP_PASSWORD_HASH:
        raise HTTPException(status_code=503, detail="登录尚未配置")
    if login_is_rate_limited(request):
        raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")
    password_valid = verify_password(body.password, config.APP_PASSWORD_HASH)
    valid = hmac.compare_digest(body.username, config.APP_USERNAME) and password_valid
    if not valid:
        await record_login_failure(request)
        raise HTTPException(status_code=401, detail="用户名或密码不正确")
    clear_login_failures(request)
    await create_session(request, response, config.APP_USERNAME)
    return {"ok": True, "data": {"username": config.APP_USERNAME}}


@router.get("/me")
async def me(principal=Depends(verify_token)):
    return {"ok": True, "data": {"username": principal["username"]}}


@router.post("/logout")
async def logout(request: Request, response: Response, _=Depends(verify_token)):
    await delete_session(request, response)
    return {"ok": True, "data": None}


@router.get("/mcp-check", include_in_schema=False)
async def mcp_check(_=Depends(verify_mcp_token)):
    """Internal Nginx auth_request target. It never returns memory data."""
    return Response(status_code=204)
