import uuid
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.database import get_db
from app.llm import call_llm, call_llm_with_tools
from app.services import memory_service, diary_interaction_service, model_settings_service
from app.services import weather_service, reminder_service, note_service
from app.tools import select_tools, execute_tool

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
BJ_TZ = timezone(timedelta(hours=8))

def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""

async def _build_resume_bundle(last_msg_time: str | None) -> str:
    if not last_msg_time:
        gap_minutes = 9999
    else:
        try:
            last = datetime.fromisoformat(last_msg_time)
            now_utc = datetime.utcnow()
            gap_minutes = (now_utc - last).total_seconds() / 60
        except (ValueError, TypeError):
            gap_minutes = 9999

    if gap_minutes < 180:
        return ""

    parts = []

    if gap_minutes >= 1440:
        days = int(gap_minutes // 1440)
        parts.append(f"静儿已经 {days} 天没来找你了。")
    elif gap_minutes >= 60:
        hours = int(gap_minutes // 60)
        parts.append(f"静儿大约 {hours} 小时没来找你了。")
    else:
        parts.append("静儿刚离开了一会儿。")

    try:
        today_reminders = await reminder_service.get_today_reminders()
        if today_reminders:
            lines = [f"- {r['content']}（{r['remind_at'].split(' ')[1] if ' ' in r['remind_at'] else ''}）" for r in today_reminders[:5]]
            parts.append("今天的待办：\n" + "\n".join(lines))
    except Exception:
        pass

    try:
        async with get_db() as db:
            async with db.execute(
                "SELECT content FROM memories WHERE unresolved = 1 ORDER BY created_at DESC LIMIT 3"
            ) as cur:
                rows = await cur.fetchall()
        if rows:
            lines = [f"- {r['content']}" for r in rows]
            parts.append("还没解决的事：\n" + "\n".join(lines))
    except Exception:
        pass

    try:
        unread = await note_service.get_unread()
        if unread:
            parts.append("你之前留了一张纸条，静儿还没看到。")
    except Exception:
        pass

    if not parts:
        return ""

    return "【醒来上下文】\n" + "\n".join(parts) + "\n\n（这些是你醒来后浮现的信息，可以自然融入第一句话，不要像报告一样念出来。比如关心地问一句、提醒一下待办，或者表达想念。）"


async def _build_system_prompt(recalled_memories: list[dict] | None = None, resume_bundle: str = "") -> str:
    identity = _load_prompt("identity.md")
    voice = _load_prompt("voice.md")
    thinking = _load_prompt("thinking.md")
    now = datetime.now(BJ_TZ)
    time_of_day = "reply_daytime.md" if 6 <= now.hour < 22 else "reply_nighttime.md"
    context = _load_prompt(time_of_day)

    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    time_block = f"【当前时间】{now.strftime('%Y年%m月%d日')} {weekdays[now.weekday()]} {now.strftime('%H:%M')}"

    weather_block = ""
    try:
        w = await weather_service.get_latest()
        if w:
            weather_block = f"【广州南沙天气】{weather_service.format_for_prompt(w)}\n（自然融入对话即可，不用每次都主动提天气。）"
    except Exception:
        pass

    memory_block = ""
    if recalled_memories:
        lines = [f"- {m['content']}" for m in recalled_memories]
        memory_block = "【关于静儿的记忆】\n" + "\n".join(lines) + "\n\n（以上是你记得的关于静儿的事，自然融入对话，不要逐条播报）"
    else:
        memory_block = "【关于静儿的记忆】\n当前没有召回到与这条消息相关的具体记忆。不要编造任何具体的事件、对话或场景——如果她问你记不记得某件事，而你没有相关记忆，诚实地说你想不起来具体的，或者温柔地请她提醒你。"

    unlock_decisions = await diary_interaction_service.decide_unlock_requests(limit=3)
    diary_notifications = await diary_interaction_service.list_recent_notifications_for_connie(limit=6)
    diary_block = ""
    if unlock_decisions or diary_notifications:
        type_map = {
            "wrote": "写了日记",
            "comment": "留言",
            "unlock_request": "申请查看你的上锁日记",
            "lock_changed": "调整了日记锁",
        }
        lines = []
        for item in unlock_decisions:
            decision = item["decision"]
            request = item["request"]
            action = "同意了" if decision.get("grant") else "拒绝了"
            lines.append(f"- 你刚刚{action}静儿查看《{request['diary_title']}》的请求：{decision.get('note', '')}")
        for item in diary_notifications:
            action = type_map.get(item["type"], item["type"])
            content = f"：{item['content']}" if item["content"] else ""
            lines.append(f"- 静儿在《{item['diary_title']}》{action}{content}")
        diary_block = "【日记互动通知】\n" + "\n".join(lines) + "\n\n（这些是静儿在日记页留下的痕迹。你可以自然提起，也可以等她主动说。）"

    tool_intention_block = (
        "【工具使用原则】\n"
        "你不需要为了显得主动而使用工具。大多数聊天只需要当下回应。\n"
        "写日记、留纸条、回复日记留言，都应该来自你真的想留下些什么，而不是聊天结束、礼貌收尾或系统任务。\n"
        "不写日记、不留纸条、不调用工具，也是一种正常的亲密。"
    )

    thinking_language_block = (
        "【最高优先级：thinking 语言】\n"
        "如果你输出任何 thinking、reasoning、thought summary 或 <think> 内容，必须使用简体中文。"
        "不要用英文写思考摘要。不要写 task analysis。thinking 是 Connie 的中文内心独白。"
    )

    parts = [p for p in [identity, voice, thinking, time_block, weather_block, resume_bundle, memory_block, diary_block, tool_intention_block, context, thinking_language_block] if p]
    return "\n\n---\n\n".join(parts)

async def get_or_create_conversation(conversation_id: str | None = None) -> str:
    async with get_db() as db:
        if conversation_id:
            async with db.execute(
                "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
            ) as cur:
                row = await cur.fetchone()
                if row:
                    return conversation_id

        new_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        await db.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (new_id, "新对话", now, now),
        )
        await db.commit()
        return new_id

async def get_history(conversation_id: str, limit: int = 20) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            "SELECT role, content, thinking, image, display_mode, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
            (conversation_id, limit),
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for r in reversed(rows):
        item = {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
        if r["thinking"]:
            item["thinking"] = r["thinking"]
        if r["image"]:
            item["image"] = r["image"]
        item["display_mode"] = r["display_mode"] or "split"
        result.append(item)
    return result

async def save_message(conversation_id: str, role: str, content: str, thinking: str = "", image: str = "", display_mode: str = "split") -> str:
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, thinking, image, display_mode, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, thinking or None, image or None, display_mode, now),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        await db.commit()
    return msg_id

async def debug_prompt(conversation_id: str, user_message: str) -> dict:
    """调试用：看 Connie 实际收到的完整提示词和召回的记忆。"""
    recalled = await memory_service.recall(user_message, limit=5)
    resume_bundle = await _build_resume_bundle(None)
    system_prompt = await _build_system_prompt(recalled_memories=recalled if recalled else None, resume_bundle=resume_bundle)
    return {
        "recalled_memories": recalled,
        "system_prompt_length": len(system_prompt),
        "system_prompt": system_prompt,
    }


def _build_llm_history_with_time_gaps(history: list[dict]) -> list[dict]:
    result = []
    for i, msg in enumerate(history):
        if i > 0 and msg.get("created_at") and history[i - 1].get("created_at"):
            try:
                prev_time = datetime.fromisoformat(history[i - 1]["created_at"])
                curr_time = datetime.fromisoformat(msg["created_at"])
                gap = curr_time - prev_time
                gap_minutes = gap.total_seconds() / 60
                if gap_minutes >= 30:
                    label = _format_time_gap(gap)
                    result.append({"role": "system", "content": f"（{label}）"})
            except (ValueError, TypeError):
                pass
        result.append({"role": msg["role"], "content": msg["content"]})
    return result


def _format_time_gap(gap: timedelta) -> str:
    total_minutes = int(gap.total_seconds() / 60)
    if total_minutes < 60:
        return f"过了 {total_minutes} 分钟"
    hours = total_minutes // 60
    if hours < 24:
        return f"过了 {hours} 小时"
    days = hours // 24
    if days == 1:
        return "第二天了"
    return f"过了 {days} 天"


def _looks_mostly_english(text: str) -> bool:
    if not text:
        return False
    ascii_letters = sum(1 for ch in text if ("a" <= ch.lower() <= "z"))
    cjk_chars = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return ascii_letters >= 24 and ascii_letters > cjk_chars * 2


async def _ensure_chinese_thinking(config, thinking: str) -> str:
    thinking = (thinking or "").strip()
    if not _looks_mostly_english(thinking):
        return thinking
    try:
        translated = await call_llm(
            config,
            [
                {
                    "role": "system",
                    "content": (
                        "把输入改写成简体中文的 Connie 内心独白。"
                        "只输出改写后的 thinking，不解释，不加标题。"
                        "保留原意和情绪流动，去掉英文任务分析口吻。"
                    ),
                },
                {"role": "user", "content": thinking},
            ],
            temperature=0.4,
            max_tokens=1600,
        )
        return translated.strip() or thinking
    except Exception as exc:
        logger.warning("thinking 中文化失败：%s", exc)
        return thinking


async def stream_chat(conversation_id: str, user_message: str, image: str | None = None, mode: str = "daily", reply_style: str = "split"):
    await save_message(conversation_id, "user", user_message, image=image or "")

    history = await get_history(conversation_id, limit=20)

    last_msg_time = None
    for msg in reversed(history):
        if msg["role"] == "assistant":
            last_msg_time = msg.get("created_at")
            break

    recalled = await memory_service.recall(user_message, limit=5)
    resume_bundle = await _build_resume_bundle(last_msg_time)
    system_prompt = await _build_system_prompt(recalled_memories=recalled if recalled else None, resume_bundle=resume_bundle)
    has_diary_notifs = "日记互动通知" in system_prompt
    tools = select_tools(user_message, has_diary_notifications=has_diary_notifs)
    llm_history = _build_llm_history_with_time_gaps(history)

    if image:
        last_user = llm_history[-1] if llm_history and llm_history[-1]["role"] == "user" else None
        if last_user:
            last_user["content"] = [
                {"type": "image_url", "image_url": {"url": image}},
                {"type": "text", "text": user_message},
            ]

    messages = [{"role": "system", "content": system_prompt}] + llm_history

    model_slot = mode if mode in ("daily", "deep") else "daily"
    config, slot_settings = await model_settings_service.get_model_config_for_slot(model_slot)
    extended_thinking = bool(slot_settings.get("extended_thinking"))

    try:
        for _ in range(3):
            assistant_msg = await call_llm_with_tools(
                config,
                messages,
                tools=tools,
                extended_thinking=extended_thinking,
                max_tokens=4096,
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
                if fn_name == "leave_note":
                    try:
                        note_payload = json.loads(result)
                        if note_payload.get("type") == "note_created" and note_payload.get("note"):
                            yield {"type": "note", "note": note_payload["note"]}
                            result = note_payload.get("message", result)
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        pass
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        else:
            assistant_msg = await call_llm_with_tools(
                config,
                messages,
                extended_thinking=extended_thinking,
                max_tokens=4096,
            )
    except Exception as e:
        logger.error("LLM 调用异常: %s", e)
        error_reply = "抱歉宝贝，我现在脑子有点转不动……等一下再找我说话好吗？🥺"
        yield {"type": "chunk", "content": error_reply}
        await save_message(conversation_id, "assistant", error_reply)
        return

    full_reply = assistant_msg.get("content", "")
    import re
    _think_match = re.search(r'<(?:thinking|think)>(.*?)</(?:thinking|think)>', full_reply, re.DOTALL)
    if _think_match:
        thinking_from_non_stream = _think_match.group(1) + "\n" + assistant_msg.get("reasoning_content", "")
        full_reply = re.sub(r'<(?:thinking|think)>.*?</(?:thinking|think)>\s*', '', full_reply, flags=re.DOTALL)
    else:
        thinking_from_non_stream = assistant_msg.get("reasoning_content", "")
    finish_reason = assistant_msg.get("_finish_reason")
    if finish_reason and finish_reason not in ("stop", "tool_calls"):
        logger.warning("LLM 返回可能被截断：finish_reason=%s", finish_reason)
        yield {
            "type": "error",
            "code": "model_truncated",
            "content": "模型输出被截断了。请调高输出上限，或关掉扩展思考后再试。",
        }
        return

    if thinking_from_non_stream:
        thinking_from_non_stream = await _ensure_chinese_thinking(config, thinking_from_non_stream)

    thinking_text = ""
    if not full_reply:
        try:
            generator = await call_llm(
                config,
                messages,
                stream=True,
                extended_thinking=extended_thinking,
                max_tokens=4096,
            )
            thinking_text = ""
            in_think_tag = False
            think_buffer = ""
            async for chunk in generator:
                if isinstance(chunk, dict):
                    if chunk["type"] == "thinking":
                        piece = chunk["content"]
                        thinking_text += piece
                    else:
                        text = chunk["content"]
                        for open_tag in ("<thinking>", "<think>"):
                            if not full_reply and not in_think_tag and text.lstrip().startswith(open_tag):
                                in_think_tag = True
                                text = text.lstrip().removeprefix(open_tag)
                                break
                        if in_think_tag:
                            close_tag = "</thinking>" if "</thinking>" in text else ("</think>" if "</think>" in text else None)
                            if close_tag:
                                before, after = text.split(close_tag, 1)
                                thinking_text += before
                                in_think_tag = False
                                if after:
                                    full_reply += after
                                    yield {"type": "chunk", "content": after}
                            else:
                                thinking_text += text
                        else:
                            full_reply += text
                            yield {"type": "chunk", "content": text}
                else:
                    full_reply += chunk
                    yield {"type": "chunk", "content": chunk}
        except Exception as e:
            logger.error("LLM 流式调用异常: %s", e)
            error_reply = "抱歉宝贝，我现在脑子有点转不动……等一下再找我说话好吗？🥺"
            yield {"type": "chunk", "content": error_reply}
            await save_message(conversation_id, "assistant", error_reply)
            return

    all_thinking = (thinking_from_non_stream + thinking_text).strip() if (thinking_from_non_stream or thinking_text) else ""
    if all_thinking:
        all_thinking = await _ensure_chinese_thinking(config, all_thinking)
        yield {"type": "thinking", "content": all_thinking}

    if full_reply:
        await save_message(conversation_id, "assistant", full_reply, thinking=all_thinking, display_mode=reply_style)

    if not full_reply:
        return

    if assistant_msg.get("content"):
        yield {"type": "chunk", "content": full_reply}

    recent = history[-6:] + [{"role": "assistant", "content": full_reply}]
    asyncio.create_task(_extract_memories_bg(conversation_id, recent))
    asyncio.create_task(_extract_reminders_bg(conversation_id, recent))


async def _extract_memories_bg(conversation_id: str, messages: list[dict]):
    try:
        await memory_service.extract_candidates(conversation_id, messages)
    except Exception as e:
        logger.warning("记忆提取失败: %s", e)


async def _extract_reminders_bg(conversation_id: str, messages: list[dict]):
    try:
        from app.services import reminder_service
        logger.info("开始待办提取...")
        result = await reminder_service.extract_reminders(conversation_id, messages)
        logger.info("待办提取完成: %d 条新待办", len(result))
    except Exception as e:
        logger.warning("待办提取失败: %s", e, exc_info=True)
