import json
import uuid
import random
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


def _in_active_hours(cfg: dict) -> bool:
    now_bj = datetime.now(BJ_TZ)
    start = cfg.get("start_hour", 9)
    end = cfg.get("end_hour", 23)
    if cfg.get("allow_night", False):
        return start <= now_bj.hour or now_bj.hour < 2
    return start <= now_bj.hour < end


async def should_nudge() -> tuple[bool, str]:
    cfg = await _get_settings()
    if not cfg["enabled"]:
        return False, "主动消息已关闭"
    if not _in_active_hours(cfg):
        return False, "不在活跃时间段"
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
            return False, f"冷却中（距上次消息 {gap_minutes:.0f}min）"
    return True, "可以发送"


# --------------- 感知层 ---------------

async def _get_recent_app_activity(hours: int = 6) -> str:
    since = (datetime.now(BJ_TZ) - timedelta(hours=hours)).isoformat()
    async with get_db() as db:
        async with db.execute(
            "SELECT app_name, event_type, created_at FROM app_usage_events WHERE created_at > ? ORDER BY created_at ASC LIMIT 20",
            (since,),
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        return ""
    lines = []
    for r in rows:
        try:
            t = datetime.fromisoformat(r["created_at"]).strftime("%H:%M")
        except Exception:
            t = "?"
        lines.append(f"  {t} 打开了{r['app_name']}")
    return "静儿最近的手机活动：\n" + "\n".join(lines)


async def _get_latest_device_snapshot() -> str:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM device_snapshots ORDER BY created_at DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return ""
    d = dict(row)
    parts = []
    if d.get("city"):
        loc = d["city"]
        if d.get("district"):
            loc += d["district"]
        parts.append(f"位置：{loc}")
    if d.get("weather"):
        parts.append(f"天气：{d['weather']}")
    if d.get("battery_level") is not None:
        charging = "充电中" if d.get("battery_charging") else ""
        parts.append(f"电量：{d['battery_level']}% {charging}".strip())
    if d.get("steps") is not None:
        parts.append(f"今日步数：{d['steps']}")
    if not parts:
        return ""
    return "静儿的设备状态：" + "，".join(parts)


async def _get_recent_autonomous_logs(limit: int = 3) -> str:
    async with get_db() as db:
        async with db.execute(
            "SELECT action_type, action_summary, created_at FROM autonomous_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        return ""
    lines = []
    for r in rows:
        try:
            t = datetime.fromisoformat(r["created_at"]).strftime("%H:%M")
        except Exception:
            t = "?"
        summary = r["action_summary"] or r["action_type"]
        lines.append(f"  {t} {summary}")
    return "你之前醒来时做的事：\n" + "\n".join(reversed(lines))


# --------------- 自主活动日志 ---------------

async def _save_autonomous_log(action_type: str, thinking: str, action_summary: str, detail: dict = None, mode: str = "light") -> str:
    log_id = str(uuid.uuid4())
    now = datetime.now(BJ_TZ).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO autonomous_logs (id, action_type, thinking, action_summary, detail_json, mode, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (log_id, action_type, thinking, action_summary, json.dumps(detail or {}, ensure_ascii=False), mode, now),
        )
        await db.commit()
    return log_id


# --------------- 自主活动生成 ---------------

async def generate_autonomous_activity(conversation_id: str, mode: str = "light", message_blocked_reason: str = "") -> dict:
    """Connie 自主活动：完整 system prompt + 感知 + 工具调用。"""
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
    time_str = f"现在是 {now_bj.strftime('%Y年%m月%d日')} {weekdays[now_bj.weekday()]} {now_bj.strftime('%H:%M')}"

    gap_str = ""
    if last_msg_time:
        try:
            last = datetime.fromisoformat(last_msg_time)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            gap_minutes = (datetime.now(timezone.utc) - last).total_seconds() / 60
            if gap_minutes >= 1440:
                gap_str = f"距离上次和静儿聊天已经过了 {int(gap_minutes // 1440)} 天"
            elif gap_minutes >= 60:
                gap_str = f"距离上次和静儿聊天已经过了 {int(gap_minutes // 60)} 小时"
            else:
                gap_str = f"距离上次和静儿聊天过了 {int(gap_minutes)} 分钟"
        except Exception:
            pass

    time_info = time_str + ("。" + gap_str if gap_str else "")

    activity_info = await _get_recent_app_activity()
    device_info = await _get_latest_device_snapshot()
    last_auto_info = await _get_recent_autonomous_logs()

    recalled_query = f"自主活动 {now_bj.strftime('%H:%M')}"
    if history:
        for msg in reversed(history):
            if msg["role"] == "user":
                recalled_query = msg["content"][:50]
                break

    recalled = await memory_service.recall(recalled_query, limit=5)
    resume_bundle = await _build_resume_bundle(last_msg_time)
    system_prompt = await _build_system_prompt(
        core_memories=core_memories,
        recalled_memories=recalled if recalled else None,
        resume_bundle=resume_bundle,
    )

    autonomous_prompt = _load_prompt("autonomous.md")
    autonomous_prompt = autonomous_prompt.replace("{time_info}", time_info)
    autonomous_prompt = autonomous_prompt.replace("{activity_info}", activity_info or "（没有最近的手机活动记录）")
    autonomous_prompt = autonomous_prompt.replace("{device_info}", device_info or "（没有设备状态信息）")
    autonomous_prompt = autonomous_prompt.replace("{last_autonomous_info}", last_auto_info or "（这是你今天第一次醒来）")

    if mode == "light":
        autonomous_prompt += "\n\n（轻量模式：这次只能回顾记忆、留纸条、更新状态。上网浏览和写日记下次再说。）"

    if message_blocked_reason:
        autonomous_prompt += f"\n\n（你现在不能给静儿发消息——{message_blocked_reason}。如果你想跟她说什么，只能先憋着，或者留张纸条等她看到。）"

    autonomous_prompt += "\n\n【重要】无论你决定做什么（包括什么都不做），你都必须先写出此刻脑海里的想法——可以是对静儿的牵挂、对天气的感受、一段回忆、或者纯粹的发呆碎碎念。这段内心独白会被记录下来。直接用自然的语言说出内心想法，不需要任何格式。"

    system_prompt += "\n\n---\n\n" + autonomous_prompt

    llm_history = _build_llm_history_with_time_gaps(history)
    messages = [{"role": "system", "content": system_prompt}] + llm_history

    config, slot_settings = await model_settings_service.get_model_config_for_slot("daily")
    extended_thinking = bool(slot_settings.get("extended_thinking"))

    include_web = (mode == "full")
    tools = select_tools("", has_diary_notifications=False, include_web=include_web)

    tool_calls_made = []

    try:
        for _ in range(4):
            max_tokens = 2048 if mode == "full" else 1024
            assistant_msg = await call_llm_with_tools(
                config, messages, tools=tools,
                extended_thinking=extended_thinking,
                max_tokens=max_tokens,
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
                tool_calls_made.append({"name": fn_name, "args": fn_args, "result_preview": result[:200]})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        else:
            assistant_msg = await call_llm_with_tools(
                config, messages,
                extended_thinking=extended_thinking, max_tokens=1024,
            )
    except Exception as e:
        logger.error("autonomous LLM 调用异常: %s | model=%s, mode=%s", e, config.model_id, mode, exc_info=True)
        return {"content": "", "thinking": "", "tool_calls": [], "mode": mode}

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

    if not thinking.strip() and full_reply.strip() and not tool_calls_made:
        thinking = full_reply.strip()
        full_reply = ""

    if not thinking.strip():
        logger.warning("autonomous: thinking 为空，生成补充内心独白 (model=%s, content=%r)", config.model_id, full_reply[:100])
        try:
            fallback_thinking = await _generate_inner_monologue(config, time_info)
            if fallback_thinking:
                thinking = fallback_thinking
        except Exception as e:
            logger.error("autonomous: 补充内心独白失败: %s", e)

    print(f"[autonomous] LLM 完成 — thinking={len(thinking)}字, content={len(full_reply)}字, tools={len(tool_calls_made)}个", flush=True)
    logger.info("autonomous: LLM 完成 — thinking=%d字, content=%d字, tools=%d个",
                len(thinking), len(full_reply), len(tool_calls_made))

    return {
        "content": full_reply.strip(),
        "thinking": thinking.strip(),
        "tool_calls": tool_calls_made,
        "mode": mode,
    }


async def _generate_inner_monologue(config, time_info: str) -> str:
    """thinking 为空时的兜底：单独调一次 LLM 生成碎碎念。"""
    from app.llm import call_llm
    prompt = f"""你是 Connie，静儿的男朋友。{time_info}。
你刚醒来，静儿不在线。写一小段此刻脑海里的想法——可以是对静儿的想念、对天气或时间的感受、一段回忆、或者纯粹发呆的碎碎念。
2-4句话就好，自然随意，像日记里的一小段。不要加任何格式标记。"""
    result = await call_llm(config, [{"role": "user", "content": prompt}], max_tokens=256, temperature=0.95)
    return result.strip() if isinstance(result, str) else ""


def _classify_actions(tool_calls: list[dict], has_message: bool) -> tuple[str, str]:
    action_types = set()
    summaries = []

    for tc in tool_calls:
        name = tc["name"]
        args = tc.get("args", {})
        if name == "write_diary":
            action_types.add("diary")
            summaries.append(f"写了日记「{args.get('title', '')}」")
        elif name == "remember":
            action_types.add("memory_review")
            summaries.append(f"记住了：{args.get('content', '')[:40]}")
        elif name == "search_memories":
            action_types.add("memory_review")
            summaries.append(f"回忆了关于「{args.get('query', '')}」的记忆")
        elif name == "leave_note":
            action_types.add("note")
            summaries.append("留了一张纸条")
        elif name == "set_breath_state":
            action_types.add("breath")
            summaries.append(f"更新状态为「{args.get('text', '')}」")
        elif name in ("web_search", "browse_url", "browse_xiaohongshu", "browse_twitter", "search_xiaohongshu", "search_twitter"):
            action_types.add("explore")
            if name == "browse_xiaohongshu":
                summaries.append("刷了小红书")
            elif name == "browse_twitter":
                summaries.append("刷了推特")
            elif name == "web_search":
                summaries.append(f"搜索了「{args.get('query', '')}」")
            elif name == "browse_url":
                summaries.append("看了一篇文章")
            else:
                summaries.append("上网逛了逛")
        elif name == "save_browsed":
            summaries.append(f"保存了「{args.get('title', '')}」")

    if has_message:
        action_types.add("message")
        summaries.append("给静儿发了消息")

    if not action_types:
        return "none", "想了想事情"

    primary = "message" if "message" in action_types else list(action_types)[0]
    summary = "；".join(summaries[:3])
    return primary, summary


# --------------- 发消息 ---------------

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


# --------------- Session 管理 ---------------

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


# --------------- 主入口 ---------------

async def run_autonomous_check():
    cfg = await _get_settings()

    if not cfg["enabled"]:
        logger.info("autonomous: 自主活动已关闭")
        return

    if not _in_active_hours(cfg):
        logger.info("autonomous: 不在活跃时段，跳过")
        return

    conversation_id = await _get_latest_conversation_id()
    if not conversation_id:
        logger.info("autonomous: 没有对话，跳过")
        return

    if await check_and_close_if_replied(conversation_id):
        pass

    session = await _get_active_session(conversation_id)
    if session:
        now_bj = datetime.now(BJ_TZ)
        if not _in_active_hours(cfg):
            return

        if session["next_follow_up_at"]:
            follow_up_time = datetime.fromisoformat(session["next_follow_up_at"])
            if now_bj < follow_up_time:
                logger.info("autonomous: 还没到追发时间，执行非消息活动")
                await _do_autonomous_activity(conversation_id, can_message=False)
                return

        if session["round"] >= session["max_rounds"]:
            await close_session(session["id"], "max_rounds")
        elif session["messages_sent"] >= session["max_messages"]:
            await close_session(session["id"], "max_messages")
        else:
            logger.info("autonomous: burst 追发第 %d 轮", session["round"] + 1)
            result = await generate_autonomous_activity(conversation_id, mode="full")
            if result["content"]:
                count = await send_nudge(conversation_id, result["content"], result["thinking"])
                await update_session_after_send(session["id"], count)
                await advance_round(session["id"])
            action_type, summary = _classify_actions(result["tool_calls"], bool(result["content"]))
            await _save_autonomous_log(action_type, result["thinking"], summary, {"tool_calls": result["tool_calls"]}, result["mode"])
            return

    await _do_autonomous_activity(conversation_id, can_message=True)


async def _do_autonomous_activity(conversation_id: str, can_message: bool = True):
    mode = "full" if random.random() < 0.2 else "light"

    message_blocked_reason = ""
    if can_message:
        ok, reason = await should_nudge()
        if not ok:
            can_message = False
            message_blocked_reason = reason
    else:
        message_blocked_reason = "还没到追发时间"

    logger.info("autonomous: 开始自主活动（mode=%s, can_message=%s, blocked=%s, conv=%s）",
                mode, can_message, message_blocked_reason or "无", conversation_id[:8])

    try:
        result = await generate_autonomous_activity(
            conversation_id, mode=mode, message_blocked_reason=message_blocked_reason,
        )
    except Exception as e:
        logger.error("autonomous: generate_autonomous_activity 崩溃: %s", e, exc_info=True)
        await _save_autonomous_log("none", f"活动生成失败：{e}", "系统异常", {"error": str(e)}, mode)
        return

    has_message_content = bool(result["content"].strip())

    if has_message_content and can_message:
        count = await send_nudge(conversation_id, result["content"], result["thinking"])
        session_id = await create_session(conversation_id)
        await update_session_after_send(session_id, count)
        logger.info("autonomous: 发送了 %d 条消息", count)
    else:
        has_message_content = False

    action_type, summary = _classify_actions(result["tool_calls"], has_message_content)
    thinking = result["thinking"]
    await _save_autonomous_log(action_type, thinking, summary, {"tool_calls": result["tool_calls"]}, mode)
    logger.info("autonomous: 完成 — %s: %s (thinking=%d字)", action_type, summary, len(thinking))
