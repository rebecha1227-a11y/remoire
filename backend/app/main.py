from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from app.database import init_db
from app.routers import chat, memory, diary, note, settings, reminder, push, signal, autonomous
from app.scheduler.jobs import connie_auto_diary, catchup_missed_diary, generate_breath_state, decay_memories, digest_memories
from app.services.nudge_service import run_autonomous_check
from app.services.weather_service import fetch_and_cache as fetch_weather
from app.services.memory_service import run_digest

scheduler = AsyncIOScheduler()


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
    scheduler.add_job(
        run_digest,
        CronTrigger(hour=2, minute=30, timezone="Asia/Shanghai"),
        id="memory_digest",
        replace_existing=True,
    )
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/api/weather")
async def get_weather():
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
async def get_chat_status():
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
