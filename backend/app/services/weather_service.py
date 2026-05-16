import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import QWEATHER_API_KEY, QWEATHER_API_HOST, QWEATHER_LOCATION
from app.database import get_db

logger = logging.getLogger(__name__)

BJ_TZ = timezone(timedelta(hours=8))


async def fetch_and_cache() -> dict | None:
    if not QWEATHER_API_KEY or not QWEATHER_API_HOST:
        logger.warning("和风天气未配置，跳过")
        return None

    url = f"https://{QWEATHER_API_HOST}/v7/weather/now"
    params = {"location": QWEATHER_LOCATION, "lang": "zh"}
    headers = {"X-QW-Api-Key": QWEATHER_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "200":
            logger.warning("和风天气返回异常: code=%s", data.get("code"))
            return None

        now_info = data["now"]
        row = {
            "temp": now_info["temp"],
            "feels_like": now_info["feelsLike"],
            "text": now_info["text"],
            "humidity": now_info["humidity"],
            "wind_dir": now_info["windDir"],
            "wind_scale": now_info["windScale"],
            "precip": now_info["precip"],
            "icon": now_info["icon"],
            "obs_time": now_info["obsTime"],
        }

        now_str = datetime.now(BJ_TZ).isoformat()
        async with get_db() as db:
            await db.execute(
                """INSERT INTO weather_cache
                   (temp, feels_like, text, humidity, wind_dir, wind_scale, precip, icon, obs_time, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["temp"], row["feels_like"], row["text"], row["humidity"],
                 row["wind_dir"], row["wind_scale"], row["precip"], row["icon"],
                 row["obs_time"], now_str),
            )
            await db.commit()

        logger.info("天气已更新: %s %s°C 体感%s°C", row["text"], row["temp"], row["feels_like"])
        return row

    except Exception as e:
        logger.error("天气获取失败: %s", e)
        return None


async def get_latest() -> dict | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM weather_cache ORDER BY fetched_at DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return dict(row)


def format_for_prompt(w: dict) -> str:
    parts = [f"{w['text']} {w['temp']}°C"]
    if w.get("feels_like") and w["feels_like"] != w["temp"]:
        parts.append(f"体感{w['feels_like']}°C")
    if w.get("humidity"):
        parts.append(f"湿度{w['humidity']}%")
    if w.get("wind_dir") and w.get("wind_scale"):
        parts.append(f"{w['wind_dir']}{w['wind_scale']}级")
    if w.get("precip") and float(w["precip"]) > 0:
        parts.append(f"降水{w['precip']}mm")
    return "，".join(parts)
