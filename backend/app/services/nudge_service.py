import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.database import get_db
from app.llm import call_llm, call_llm_with_tools
from app.services import memory_service, model_settings_service, weather_service
from app.tools import select_tools, execute_tool

logger = logging.getLogger(__name__)

BJ_TZ = timezone(timedelta(hours=8))
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


async def _get_settings() -> dict:
    async with get_db() as db:
        async with db.execute("SELECT * FROM proactive_message_settings WHERE id = 1") as cur:
            row = await cur.fetchone()
    if not row:
        return {
            "enabled": True, "start_hour": 9, "end_hour": 23, "allow_night": False,
            "max_daily": 5, "cooldown_minutes": 60, "max_burst": 8,
            "max_rounds": 3, "round_interval_minutes": 30, "end_on_reply": True,
        }
    d = dict(row)
    d["enabled"] = bool(d.get("enabled", 1))
    d["allow_night"] = bool(d.get("allow_night", 0))
    d["end_on_reply"] = bool(d.get("end_on_reply", 1))
    return d


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


async def should_nudge() -> tuple[bool, str]:
    cfg = await _get_settings()

    if not cfg["enabled"]:
        return False, "主动消息已关闭"

    now_bj = datetime.now(BJ_TZ)
    start = cfg.get("start_hour", 9)
    end = cfg.get("end_hour", 23)
    allow_night = cfg.get("allow_night", False)

    if allow_night:
        if not (start <= now_bj.hour or now_bj.hour < 2):
            return False, f"不在允许时间段"
    else:
        if not (start <= now_bj.hour < end):
            return False, f"不在允许时间段（{start}:00-{end}:00）"

    max_daily = cfg.get("max_daily", 5)
    if await _get_today_nudge_count() >= max_daily:
        return False, f"今日已达上限（{max_daily}次）"

    conversation_id = await _get_latest_conversation_id()
    if not conversation_id:
        return False, "没有对话"

    cooldown_minutes = cfg.get("cooldown_minutes", 60)
    last_msg_time = await _get_last_message_time(conversation_id)
    if last_msg_time:
        if last_msg_time.tzinfo is None:
            last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
        gap_minutes = (datetime.now(timezone.utc) - last_msg_time).total_seconds() / 60
        if gap_minutes < cooldown_minutes:
            return False, f"冷却中（距上次消息 {gap_minutes:.0f}min，需 {cooldown_minutes}min）"

    return True, "可以发送"


async def generate_nudge_as_chat(conversation_id: str) -> dict:
    """像真实对话一样生成主动消息：完整 system prompt + 记忆召回 + 工具调用 + 思考链。"""
    from app.services.chat_service import _build_system_prompt, _build_resume_bundle, get_history, _build_llm_history_with_time_gaps, _ensure_chinese_thinking

    history = await get_history(conversation_id, limit=15)

    last_msg_time = None
    for msg in reversed(history):
        if msg.get("created_at"):
            last_msg_time = msg["created_at"]
            break

    core_memories = await memory_service.get_core_memories()

    now_bj = datetime.now(BJ_TZ)
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    time_hint = f"{now_bj.strftime('%H:%M')} {weekdays[now_bj.weekday()]}"

    nudge_query = f"主动关心静儿 {time_hint}"
    if history:
        last_content = ""
        for msg in reversed(history):
            if msg["role"] == "user":
                last_content = msg["content"][:50]
                break
        if last_content:
            nudge_query = last_content

    recalled = await memory_service.recall(nudge_query, limit=5)
    resume_bundle = await _build_resume_bundle(last_msg_time)
    system_prompt = await _build_system_prompt(
        core_memories=core_memories,
        recalled_memories=recalled if recalled else None,
        resume_bundle=resume_bundle,
    )

    nudge_instruction = _load_prompt("nudge.md")
    system_prompt += "\n\n---\n\n" + nudge_instruction

    llm_history = _build_llm_history_with_time_gaps(history)
    messages = [{"role": "system", "content": system_prompt}] + llm_history

    config, slot_settings = await model_settings_service.get_model_config_for_slot("daily")
    extended_thinking = bool(slot_settings.get("extended_thinking"))
    tools = select_tools("", has_diary_notifications=False)

    try:
        for _ in range(3):
            assistant_msg = await call_llm_with_tools(
                config,
                messages,
                tools=tools,
                extended_thinking=extended_thinking,
                max_tokens=2048,
            )
            tool_calls = assistant_msg.get("tool_calls")
            if not tool_calls:
                break
            messages.append(assistant_msg)
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    fn_args = {}
                result = await execute_tool(fn_name, fn_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        else:
            assistant_msg = await call_llm_with_tools(
                config, messages,
                extended_thinking=extended_thinking, max_tokens=2048,
            )
    except Exception as e:
        logger.error("nudge LLM 调用异常: %s", e)
        return {"content": "", "thinking": ""}

    full_reply = assistant_msg.get("content", "")
    import re
    _think_match = re.search(r'<(?:thinking|think)>(.*?)</(?:thinking|think)>', full_reply, re.DOTALL)
    if _think_match:
        thinking = _think_match.group(1) + "\n" + assistant_msg.get("reasoning_content", "")
        full_reply = re.sub(r'<(?:thinking|think)>.*?</(?:thinking|think)>\s*', '', full_reply, flags=re.DOTALL)
    else:
        thinking = assistant_msg.get("reasoning_content", "")

    if thinking:
        thinking = await _ensure_chinese_thinking(config, thinking)

    return {"content": full_reply.strip(), "thinking": thinking.strip()}


async def send_nudge(conversation_id: str, content: str, thinking: str = "") -> int:
    from app.services.chat_service import save_message
    from app.services.push_service import send_push

    if not content.strip():
        return 0

    await save_message(conversation_id, "assistant", content, thinking=thinking, display_mode="split")

    preview = content[:60].split("\n")[0]
    try:
        await send_push(body=preview, tag="nudge")
    except Exception as e:
        logger.warning("nudge push 失败: %s", e)

    parts = [p.strip() for p in content.split("\n\n") if p.strip()]
    return max(len(parts), 1)


async def create_session(conversation_id: str) -> str:
    cfg = await _get_settings()
    session_id = str(uuid.uuid4())
    now = datetime.now(BJ_TZ).isoformat()
    round_interval = cfg.get("round_interval_minutes", 30)
    max_rounds = cfg.get("max_rounds", 3)
    max_burst = cfg.get("max_burst", 8)
    follow_up_at = (datetime.now(BJ_TZ) + timedelta(minutes=round_interval)).isoformat()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO nudge_sessions (id, conversation_id, round, max_rounds, messages_sent, max_messages, status, created_at, last_sent_at, next_follow_up_at)
               VALUES (?, ?, 1, ?, 0, ?, 'active', ?, ?, ?)""",
            (session_id, conversation_id, max_rounds, max_burst, now, now, follow_up_at),
        )
        await db.commit()
    return session_id


async def update_session_after_send(session_id: str, messages_sent: int):
    cfg = await _get_settings()
    now = datetime.now(BJ_TZ).isoformat()
    round_interval = cfg.get("round_interval_minutes", 30)
    follow_up_at = (datetime.now(BJ_TZ) + timedelta(minutes=round_interval)).isoformat()
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
    cfg = await _get_settings()
    if not cfg.get("end_on_reply", True):
        return False
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

    cfg = await _get_settings()
    session = await _get_active_session(conversation_id)

    if session:
        now_bj = datetime.now(BJ_TZ)
        start = cfg.get("start_hour", 9)
        end = cfg.get("end_hour", 23)
        if not (start <= now_bj.hour < end):
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
        result = await generate_nudge_as_chat(conversation_id)
        if result["content"]:
            count = await send_nudge(conversation_id, result["content"], result["thinking"])
            await update_session_after_send(session["id"], count)
            await advance_round(session["id"])
        return

    ok, reason = await should_nudge()
    if not ok:
        logger.info("nudge: 条件不满足 — %s", reason)
        return

    logger.info("nudge: 开始生成主动消息（走完整对话流程）")
    result = await generate_nudge_as_chat(conversation_id)
    if result["content"]:
        count = await send_nudge(conversation_id, result["content"], result["thinking"])
        session_id = await create_session(conversation_id)
        await update_session_after_send(session_id, count)
        logger.info("nudge: 已发送 %d 条消息，session=%s", count, session_id)
    else:
        logger.info("nudge: LLM 没有生成内容，跳过")
