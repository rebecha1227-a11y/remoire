from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import init_db
from app.routers import chat, memory, diary, note, settings
from app.scheduler.jobs import connie_auto_diary

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.add_job(
        connie_auto_diary,
        CronTrigger(hour=23, minute=0, timezone="Asia/Shanghai"),
        id="connie_auto_diary",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()

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

@app.get("/")
async def root():
    return {"ok": True, "message": "Remoire 后端运行中 🌸"}
