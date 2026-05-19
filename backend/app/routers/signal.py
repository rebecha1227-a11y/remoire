import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from pydantic import BaseModel
from app.database import get_db

router = APIRouter(prefix="/api/signal", tags=["signal"])

BJ_TZ = timezone(timedelta(hours=8))


class AppEventRequest(BaseModel):
    app_name: str
    event_type: str = "open"


class DeviceSnapshotRequest(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    district: str | None = None
    weather: str | None = None
    battery_level: int | None = None
    battery_charging: bool | None = None
    steps: int | None = None


@router.post("/app-event")
async def report_app_event(req: AppEventRequest):
    now = datetime.now(BJ_TZ)
    now_str = now.isoformat()
    five_min_ago = (now - timedelta(minutes=5)).isoformat()

    async with get_db() as db:
        async with db.execute(
            "SELECT 1 FROM app_usage_events WHERE app_name = ? AND created_at > ? LIMIT 1",
            (req.app_name, five_min_ago),
        ) as cur:
            if await cur.fetchone():
                return {"ok": True, "deduped": True}

        await db.execute(
            "INSERT INTO app_usage_events (id, app_name, event_type, created_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), req.app_name, req.event_type, now_str),
        )
        await db.commit()
    return {"ok": True}


@router.post("/device-snapshot")
async def report_device_snapshot(req: DeviceSnapshotRequest):
    now_str = datetime.now(BJ_TZ).isoformat()
    import json
    async with get_db() as db:
        await db.execute(
            """INSERT INTO device_snapshots (id, latitude, longitude, city, district, weather,
               battery_level, battery_charging, steps, raw_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), req.latitude, req.longitude,
                req.city, req.district, req.weather,
                req.battery_level, int(req.battery_charging) if req.battery_charging is not None else None,
                req.steps, json.dumps(req.model_dump(), ensure_ascii=False), now_str,
            ),
        )
        await db.commit()
    return {"ok": True}


@router.get("/recent-activity")
async def get_recent_activity(hours: int = 6):
    since = (datetime.now(BJ_TZ) - timedelta(hours=hours)).isoformat()
    async with get_db() as db:
        async with db.execute(
            "SELECT app_name, event_type, created_at FROM app_usage_events WHERE created_at > ? ORDER BY created_at DESC LIMIT 30",
            (since,),
        ) as cur:
            events = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT city, district, weather, battery_level, battery_charging, steps, created_at FROM device_snapshots WHERE created_at > ? ORDER BY created_at DESC LIMIT 5",
            (since,),
        ) as cur:
            snapshots = [dict(r) for r in await cur.fetchall()]

    return {"ok": True, "data": {"app_events": events, "device_snapshots": snapshots}}
