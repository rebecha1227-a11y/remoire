import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.database import get_db
from app.llm import call_llm
from app.services import memory_service, model_settings_service, weather_service

logger = logging.getLogger(__name__)

BJ_TZ = timezone(timedelta(hours=8))
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

ALLOWED_HOUR_START = 9
ALLOWED_HOUR_END = 23
COOLDOWN_HOURS = 4
DAILY_LIMIT = 5
BURST_MAX_ROUNDS = 3
BURST_MAX_MESSAGES = 8
BURST_FOLLOW_UP_MINUTES = 30


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


async def _get_last_message_time(conversation_id: str) -> datetime | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT created_at FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1",
            (conversation_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    try:
        return datetime.fromisoformat(row["created_at"])
    except (ValueError, TypeError):
        return None


async def _get_last_user_message_time(conversation_id: str) -> datetime | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT created_at FROM messages WHERE conversation_id = ? AND role = 'user' ORDER BY created_at DESC LIMIT 1",
            (conversation_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    try:
        return datetime.fromisoformat(row["created_at"])
    except (ValueError, TypeError):
        return None


async def _get_today_nudge_count() -> int:
    today_start = datetime.now(BJ_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM nudge_sessions WHERE created_at >= ?",
            (today_start.isoformat(),),
        ) as cur:
            row = await cur.fetchone()
    return row["cnt"] if row else 0


async def _get_active_session(conversation_id: str) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM nudge_sessions WHERE conversation_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
            (conversation_id,),
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def _get_latest_conversation_id() -> str | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM conversations ORDER BY updated_at DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    return row["id"] if row else None


async def _check_user_replied_since(conversation_id: str, since: str) -> bool:
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ? AND role = 'user' AND created_at > ?",
            (conversation_id, since),
        ) as cur:
            row = await cur.fetchone()
    return (row["cnt"] or 0) > 0


async def _is_enabled() -> bool:
    async with get_db() as db:
        async with db.execute(
            "SELECT enabled FROM proactive_message_settings WHERE id = 1"
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return True
    return bool(row["enabled"])


async def should_nudge() -> tuple[bool, str]:
    if not await _is_enabled():
        return False, "主动消息已关闭"

    now_bj = datetime.now(BJ_TZ)

    if not (ALLOWED_HOUR_START <= now_bj.hour < ALLOWED_HOUR_END):
        return False, f"不在允许时间段（{ALLOWED_HOUR_START}:00-{ALLOWED_HOUR_END}:00）"

    if await _get_today_nudge_count() >= DAILY_LIMIT:
        return False, f"今日已达上限（{DAILY_LIMIT}次）"

    conversation_id = await _get_latest_conversation_id()
    if not conversation_id:
        return False, "没有对话"

    last_msg_time = await _get_last_message_time(conversation_id)
    if last_msg_time:
        if last_msg_time.tzinfo is None:
            last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
        gap_hours = (datetime.now(timezone.utc) - last_msg_time).total_seconds() / 3600
        if gap_hours < COOLDOWN_HOURS:
            return False, f"冷却中（距上次消息 {gap_hours:.1f}h，需 {COOLDOWN_HOURS}h）"

    return True, "可以发送"


async def _build_nudge_context(conversation_id: str) -> str:
    now_bj = datetime.now(BJ_TZ)
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    parts = [f"当前时间：{now_bj.strftime('%Y年%m月%d日')} {weekdays[now_bj.weekday()]} {now_bj.strftime('%H:%M')}"]

    last_msg_time = await _get_last_message_time(conversation_id)
    if last_msg_time:
        if last_msg_time.tzinfo is None:
            last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
        gap = datetime.now(timezone.utc) - last_msg_time
        hours = gap.total_seconds() / 3600
        if hours >= 24:
            parts.append(f"距离上次聊天：{int(hours // 24)} 天")
        else:
            parts.append(f"距离上次聊天：{int(hours)} 小时")

    try:
        w = await weather_service.get_latest()
        if w:
            parts.append(f"天气：{weather_service.format_for_prompt(w)}")
    except Exception:
        pass

    async with get_db() as db:
        async with db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 8",
            (conversation_id,),
        ) as cur:
            rows = await cur.fetchall()
    if rows:
        recent = [f"{'静儿' if r['role'] == 'user' else 'Connie'}: {r['content'][:100]}" for r in reversed(rows)]
        parts.append("最近聊天：\n" + "\n".join(recent))

    recalled = await memory_service.recall("主动关心静儿", limit=3)
    if recalled:
        parts.append("相关记忆：\n" + "\n".join(f"- {m['content']}" for m in recalled))

    return "\n\n".join(parts)


async def generate_nudge(conversation_id: str) -> list[str]:
    context = await _build_nudge_context(conversation_id)
    prompt_template = _load_prompt("nudge.md")
    prompt = prompt_template.replace("{context}", context)

    identity = _load_prompt("identity.md").replace("{user}", "静儿")
    voice = _load_prompt("voice.md").replace("{user}", "静儿")

    config, _ = await model_settings_service.get_model_config_for_slot("daily")
    result = await call_llm(
        config,
        [
            {"role": "system", "content": identity + "\n\n---\n\n" + voice},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=300,
        extended_thinking=False,
    )

    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        messages = json.loads(result)
        if isinstance(messages, list) and all(isinstance(m, str) for m in messages):
            return messages[:3]
    except (json.JSONDecodeError, TypeError):
        pass

    if result.startswith("["):
        try:
            messages = json.loads(result.split("\n")[0])
            if isinstance(messages, list):
                return [str(m) for m in messages[:3]]
        except Exception:
            pass

    return [result] if result else ["想你了"]


async def send_nudge(conversation_id: str, messages: list[str]) -> int:
    from app.services.chat_service import save_message
    from app.services.push_service import send_push
    count = 0
    for msg in messages:
        if not msg.strip():
            continue
        await save_message(conversation_id, "assistant", msg.strip(), display_mode="split")
        count += 1
    if count > 0:
        preview = messages[0][:60] if messages else ""
        try:
            await send_push(body=preview, tag="nudge")
        except Exception as e:
            logger.warning("nudge push 失败: %s", e)
    return count


async def create_session(conversation_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(BJ_TZ).isoformat()
    follow_up_at = (datetime.now(BJ_TZ) + timedelta(minutes=BURST_FOLLOW_UP_MINUTES)).isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO nudge_sessions (id, conversation_id, round, max_rounds, messages_sent, max_messages, status, created_at, last_sent_at, next_follow_up_at)
               VALUES (?, ?, 1, ?, 0, ?, 'active', ?, ?, ?)""",
            (session_id, conversation_id, BURST_MAX_ROUNDS, BURST_MAX_MESSAGES, now, now, follow_up_at),
        )
        await db.commit()
    return session_id


async def update_session_after_send(session_id: str, messages_sent: int):
    now = datetime.now(BJ_TZ).isoformat()
    follow_up_at = (datetime.now(BJ_TZ) + timedelta(minutes=BURST_FOLLOW_UP_MINUTES)).isoformat()
    async with get_db() as db:
        await db.execute(
            """UPDATE nudge_sessions
               SET messages_sent = messages_sent + ?, last_sent_at = ?, next_follow_up_at = ?
               WHERE id = ?""",
            (messages_sent, now, follow_up_at, session_id),
        )
        await db.commit()


async def advance_round(session_id: str):
    async with get_db() as db:
        await db.execute(
            "UPDATE nudge_sessions SET round = round + 1 WHERE id = ?",
            (session_id,),
        )
        await db.commit()


async def close_session(session_id: str, reason: str = "completed"):
    async with get_db() as db:
        await db.execute(
            "UPDATE nudge_sessions SET status = ? WHERE id = ?",
            (reason, session_id),
        )
        await db.commit()


async def check_and_close_if_replied(conversation_id: str) -> bool:
    session = await _get_active_session(conversation_id)
    if not session:
        return False
    if await _check_user_replied_since(conversation_id, session["last_sent_at"]):
        await close_session(session["id"], "user_replied")
        logger.info("用户已回复，关闭 nudge session %s", session["id"])
        return True
    return False


async def run_nudge_check():
    conversation_id = await _get_latest_conversation_id()
    if not conversation_id:
        logger.info("nudge: 没有对话，跳过")
        return

    if await check_and_close_if_replied(conversation_id):
        return

    session = await _get_active_session(conversation_id)

    if session:
        now_bj = datetime.now(BJ_TZ)
        if not (ALLOWED_HOUR_START <= now_bj.hour < ALLOWED_HOUR_END):
            logger.info("nudge: 不在允许时间段，跳过 burst 追发")
            return

        if session["next_follow_up_at"]:
            follow_up_time = datetime.fromisoformat(session["next_follow_up_at"])
            if now_bj < follow_up_time:
                logger.info("nudge: 还没到追发时间，跳过")
                return

        if session["round"] >= session["max_rounds"]:
            await close_session(session["id"], "max_rounds")
            logger.info("nudge: 达到最大轮次，关闭 session")
            return

        if session["messages_sent"] >= session["max_messages"]:
            await close_session(session["id"], "max_messages")
            logger.info("nudge: 达到最大消息数，关闭 session")
            return

        logger.info("nudge: burst 追发第 %d 轮", session["round"] + 1)
        messages = await generate_nudge(conversation_id)
        remaining = session["max_messages"] - session["messages_sent"]
        messages = messages[:remaining]
        count = await send_nudge(conversation_id, messages)
        await update_session_after_send(session["id"], count)
        await advance_round(session["id"])
        return

    ok, reason = await should_nudge()
    if not ok:
        logger.info("nudge: 条件不满足 — %s", reason)
        return

    logger.info("nudge: 开始生成主动消息")
    messages = await generate_nudge(conversation_id)
    count = await send_nudge(conversation_id, messages)
    session_id = await create_session(conversation_id)
    await update_session_after_send(session_id, count)
    logger.info("nudge: 已发送 %d 条消息，session=%s", count, session_id)
