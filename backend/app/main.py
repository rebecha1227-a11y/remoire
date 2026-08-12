from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from app.database import init_db
from app.auth import verify_token
from app.config import ALLOWED_HOSTS, TRUSTED_ORIGINS
from app.routers import auth, chat, memory, diary, note, settings, reminder, push, signal, autonomous
from app.scheduler.jobs import connie_auto_diary, catchup_missed_diary, generate_breath_state, decay_memories, digest_memories
from app.services.nudge_service import run_autonomous_check
from app.services.model_settings_service import migrate_preset_secrets
from app.services.weather_service import fetch_and_cache as fetch_weather
import logging
import re
import time
import uuid

scheduler = AsyncIOScheduler()
logger = logging.getLogger("remoire.http")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _schedule_next_autonomous():
    import random, logging
    from datetime import datetime, timedelta
    delay_minutes = random.randint(45, 75)
    run_time = datetime.now() + timedelta(minutes=delay_minutes)
    scheduler.add_job(
        _run_autonomous_and_reschedule,
        DateTrigger(run_date=run_time),
        id="autonomous_check",
        replace_existing=True,
    )
    print(f"[autonomous] 下次活动在 {delay_minutes} 分钟后（{run_time.strftime('%H:%M')}）", flush=True)


async def _run_autonomous_and_reschedule():
    try:
        await run_autonomous_check()
    finally:
        _schedule_next_autonomous()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    migrated_secrets = await migrate_preset_secrets()
    if migrated_secrets:
        logger.info("encrypted_model_preset_secrets=%s", migrated_secrets)
    scheduler.add_job(
        connie_auto_diary,
        CronTrigger(hour=23, minute=0, timezone="Asia/Shanghai"),
        id="connie_auto_diary",
        replace_existing=True,
    )
    scheduler.add_job(
        generate_breath_state,
        CronTrigger(hour=10, minute=0, timezone="Asia/Shanghai"),
        id="generate_breath_state",
        replace_existing=True,
    )
    scheduler.add_job(
        fetch_weather,
        CronTrigger(hour="8,20", minute=0, timezone="Asia/Shanghai"),
        id="fetch_weather",
        replace_existing=True,
    )
    scheduler.add_job(
        decay_memories,
        CronTrigger(hour=3, minute=0, timezone="Asia/Shanghai"),
        id="decay_memories",
        replace_existing=True,
    )
    scheduler.add_job(
        digest_memories,
        CronTrigger(hour=3, minute=30, timezone="Asia/Shanghai"),
        id="digest_memories",
        replace_existing=True,
    )
    _schedule_next_autonomous()
    scheduler.start()
    await catchup_missed_diary()
    await generate_breath_state()
    await fetch_weather()
    yield
    scheduler.shutdown()
    try:
        from app.services.web_service import close_browser
        await close_browser()
    except Exception:
        pass

app = FastAPI(lifespan=lifespan)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=TRUSTED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    incoming_id = request.headers.get("x-request-id", "")
    request_id = incoming_id if _SAFE_REQUEST_ID.fullmatch(incoming_id) else str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id, request.method, request.url.path, response.status_code, duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["Cache-Control"] = "no-store"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def _error_response(request: Request, status_code: int, code: str, message: str, headers=None):
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "ok": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
            },
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "请求未能完成"
    return _error_response(request, exc.status_code, f"http_{exc.status_code}", message, exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, _exc: RequestValidationError):
    return _error_response(request, 422, "validation_error", "请求参数不正确")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("request_id=%s unhandled_error", getattr(request.state, "request_id", None), exc_info=exc)
    return _error_response(request, 500, "internal_error", "服务暂时出了点问题")

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(diary.router)
app.include_router(note.router)
app.include_router(settings.router)
app.include_router(reminder.router)
app.include_router(push.router)
app.include_router(signal.router)
app.include_router(autonomous.router)

@app.get("/")
async def root():
    return {"ok": True, "message": "Remoire 后端运行中 🌸"}


@app.get("/api/health/live")
async def health_live():
    return {"ok": True, "data": {"status": "alive"}, "error": None}


@app.get("/api/health/ready")
async def health_ready():
    from app.database import get_db
    try:
        async with get_db() as db:
            row = await (await db.execute("SELECT 1")).fetchone()
        if not row:
            raise RuntimeError("database probe returned no row")
    except Exception:
        raise HTTPException(status_code=503, detail="数据库尚未就绪")
    return {"ok": True, "data": {"status": "ready"}, "error": None}

@app.get("/api/weather")
async def get_weather(_=Depends(verify_token)):
    from datetime import datetime, timedelta, timezone
    from app.services.weather_service import get_latest, fetch_and_cache
    w = await get_latest()
    if w and w.get("fetched_at"):
        bj_tz = timezone(timedelta(hours=8))
        try:
            fetched = datetime.fromisoformat(w["fetched_at"])
            if datetime.now(bj_tz) - fetched > timedelta(hours=3):
                fresh = await fetch_and_cache()
                if fresh:
                    w = await get_latest()
        except Exception:
            pass
    elif not w:
        await fetch_and_cache()
        w = await get_latest()
    if not w:
        return {"ok": True, "data": None}
    return {"ok": True, "data": w}

@app.get("/api/chat/status")
async def get_chat_status(_=Depends(verify_token)):
    from app.database import get_db
    async with get_db() as db:
        async with db.execute(
            "SELECT content FROM breath_states ORDER BY created_at DESC LIMIT 1"
        ) as cur:
            breath_row = await cur.fetchone()
        async with db.execute(
            "SELECT id, content AS title, remind_at AS due_at FROM reminders WHERE status = 'pending' AND remind_at >= datetime('now') ORDER BY remind_at ASC LIMIT 1"
        ) as cur:
            reminder_row = await cur.fetchone()
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM notes WHERE is_read = 0"
        ) as cur:
            notes_row = await cur.fetchone()
    return {"ok": True, "data": {
        "presence_text": breath_row["content"] if breath_row else None,
        "today_reminder": dict(reminder_row) if reminder_row else None,
        "unread_notes_count": notes_row["cnt"] if notes_row else 0,
    }}
