import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter
from app.database import get_db

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])

BJ_TZ = timezone(timedelta(hours=8))


@router.get("/logs")
async def get_logs(date: str | None = None):
    if date:
        day_start = f"{date}T00:00:00+08:00"
        day_end = f"{date}T23:59:59+08:00"
    else:
        now = datetime.now(BJ_TZ)
        day_start = now.replace(hour=0, minute=0, second=0).isoformat()
        day_end = now.replace(hour=23, minute=59, second=59).isoformat()

    async with get_db() as db:
        async with db.execute(
            """SELECT id, action_type, thinking, action_summary, detail_json, mode, created_at
               FROM autonomous_logs
               WHERE created_at >= ? AND created_at <= ?
               ORDER BY created_at ASC""",
            (day_start, day_end),
        ) as cur:
            rows = await cur.fetchall()

    logs = []
    for r in rows:
        d = dict(r)
        try:
            d["detail"] = json.loads(d.pop("detail_json", "{}") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["detail"] = {}
        logs.append(d)

    return {"ok": True, "data": logs}


@router.get("/dates")
async def get_active_dates(month: str | None = None):
    if month:
        month_start = f"{month}-01T00:00:00+08:00"
        parts = month.split("-")
        year, mon = int(parts[0]), int(parts[1])
        if mon == 12:
            month_end = f"{year + 1}-01-01T00:00:00+08:00"
        else:
            month_end = f"{year}-{mon + 1:02d}-01T00:00:00+08:00"
    else:
        now = datetime.now(BJ_TZ)
        month_start = now.replace(day=1, hour=0, minute=0, second=0).isoformat()
        if now.month == 12:
            month_end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0).isoformat()
        else:
            month_end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0).isoformat()

    async with get_db() as db:
        async with db.execute(
            """SELECT DISTINCT substr(created_at, 1, 10) as date_str
               FROM autonomous_logs
               WHERE created_at >= ? AND created_at < ?
               ORDER BY date_str""",
            (month_start, month_end),
        ) as cur:
            rows = await cur.fetchall()

    dates = [r["date_str"] for r in rows]
    return {"ok": True, "data": dates}
