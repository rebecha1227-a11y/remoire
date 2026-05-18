import json
import uuid
import logging
from datetime import datetime, timezone
from app.database import get_db
from app.config import VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CONTACT

logger = logging.getLogger(__name__)

_user_active: bool = False
_last_active_at: float = 0


def set_presence(active: bool):
    global _user_active, _last_active_at
    import time
    _user_active = active
    if active:
        _last_active_at = time.time()


def is_user_active() -> bool:
    import time
    if not _user_active:
        return False
    if (time.time() - _last_active_at) > 120:
        return False
    return True


async def save_subscription(endpoint: str, p256dh: str, auth: str, user_agent: str = "", display_name: str = "Connie") -> str:
    sub_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    async with get_db() as db:
        existing = await db.execute(
            "SELECT id FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
        )
        row = await existing.fetchone()
        if row:
            await db.execute(
                "UPDATE push_subscriptions SET p256dh = ?, auth = ?, user_agent = ?, display_name = ?, last_used_at = ? WHERE id = ?",
                (p256dh, auth, user_agent, display_name, now, row["id"]),
            )
            await db.commit()
            return row["id"]
        await db.execute(
            "INSERT INTO push_subscriptions (id, endpoint, p256dh, auth, user_agent, display_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sub_id, endpoint, p256dh, auth, user_agent, display_name, now),
        )
        await db.commit()
    return sub_id


async def remove_subscription(endpoint: str):
    async with get_db() as db:
        await db.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
        await db.commit()


async def get_all_subscriptions() -> list[dict]:
    async with get_db() as db:
        async with db.execute("SELECT * FROM push_subscriptions") as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_display_name() -> str:
    async with get_db() as db:
        async with db.execute("SELECT display_name FROM push_subscriptions LIMIT 1") as cur:
            row = await cur.fetchone()
    if row and row["display_name"]:
        return row["display_name"]
    return "Connie"


async def update_display_name(name: str):
    async with get_db() as db:
        await db.execute("UPDATE push_subscriptions SET display_name = ?", (name,))
        await db.commit()


async def send_push(title: str | None = None, body: str = "", url: str = "/", tag: str = "remoire", skip_if_active: bool = True):
    if skip_if_active and is_user_active():
        logger.info("push: 用户在线，跳过推送")
        return 0

    if not VAPID_PRIVATE_KEY:
        logger.warning("push: VAPID_PRIVATE_KEY 未配置，跳过推送")
        return 0

    subs = await get_all_subscriptions()
    if not subs:
        logger.info("push: 没有订阅，跳过")
        return 0

    if title is None:
        title = await get_display_name()

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "tag": tag,
    }, ensure_ascii=False)

    sent = 0
    for sub in subs:
        try:
            from pywebpush import webpush, WebPushException
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CONTACT},
            )
            sent += 1
            async with get_db() as db:
                await db.execute(
                    "UPDATE push_subscriptions SET last_used_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), sub["id"]),
                )
                await db.commit()
        except Exception as e:
            error_str = str(e)
            if "410" in error_str or "404" in error_str:
                logger.info("push: 订阅已失效，删除 %s", sub["id"])
                await remove_subscription(sub["endpoint"])
            else:
                logger.warning("push: 发送失败 %s — %s", sub["id"], e)

    logger.info("push: 发送 %d/%d 成功", sent, len(subs))
    return sent
