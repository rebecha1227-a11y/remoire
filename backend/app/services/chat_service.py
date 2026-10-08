from app.services import prompt_profile_service
import uuid
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.database import get_db
from app.llm import call_llm, call_llm_with_tools
from app.services import memory_service, diary_interaction_service, model_settings_service
from app.services import context_budget_service
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

    if gap_minutes < 120:
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

    try:
        since = last_msg_time or ""
        if since:
            async with get_db() as db:
                async with db.execute(
                    """SELECT action_type, action_summary, thinking, created_at
                       FROM autonomous_logs
                       WHERE created_at > ? AND action_type != 'none'
                       ORDER BY created_at ASC LIMIT 10""",
                    (since,),
                ) as cur:
                    auto_rows = await cur.fetchall()
            if auto_rows:
                auto_lines = []
                for r in auto_rows:
                    try:
                        t = datetime.fromisoformat(r["created_at"]).strftime("%H:%M")
                    except Exception:
                        t = "?"
                    auto_lines.append(f"  {t} {r['action_summary']}")
                parts.append("你不在的时候做的事：\n" + "\n".join(auto_lines))
    except Exception:
        pass

    if not parts:
        return ""

    return "【醒来上下文】\n" + "\n".join(parts) + "\n\n（这些是你醒来后浮现的信息，包括你在她不在时做过的事。可以自然融入对话，不要像报告一样念出来。你记得自己做过什么——发过的消息、写过的日记、看过的文章——它们是你的经历。）"


def _join_prompt_parts(parts: list[str]) -> str:
    return "\n\n---\n\n".join(part for part in parts if part)


def _deduplicate_core_memories(memories: list[dict]) -> list[dict]:
    """Fold only identical text; similar wording can encode different facts."""
    seen = set()
    result = []
    for memory in memories:
        content = memory.get("content") or ""
        if content not in seen:
            seen.add(content)
            result.append(memory)
    return result


def _memory_block(core_memories: list[dict], recalled_memories: list[dict]) -> str:
    memory_parts = []
    if core_memories:
        memory_parts.append("【核心记忆 · 永远记住】\n" + "\n".join(_memory_prompt_line(m) for m in core_memories))
    if recalled_memories:
        memory_parts.append("【与当前对话相关的记忆】\n" + "\n".join(_memory_prompt_line(m) for m in recalled_memories))
    if memory_parts:
        return "\n\n".join(memory_parts) + "\n\n（以上是历史记忆，不保证描述仍适用于现在；意识层是主观感受而非静儿确认的事实。自然融入，不逐条播报；以她当前明确说明和事件时间为准。未列出的记忆不代表不存在。）"
    return "【关于静儿的记忆】\n本轮没有装载具体记忆。不要编造任何具体事件、对话或场景；如果她问你记不记得某件事，而当前上下文没有依据，诚实地说想不起具体内容，或者温柔地请她提醒你。"


async def _collect_system_prompt_parts(
    core_memories: list[dict] | None = None,
    recalled_memories: list[dict] | None = None,
    resume_bundle: str = "",
    *,
    scene: bool = False,
) -> dict:
    profiles = await prompt_profile_service.load_runtime_profiles()
    profile_parts = [profiles["identity"]["content"], profiles["voice"]["content"]]
    if scene and profiles["scene"]["enabled"]:
        profile_parts.append(profiles["scene"]["content"])
    thinking = _load_prompt("thinking.md")
    grounding = _load_prompt("grounding.md")
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

    return {
        "profile_parts": [part for part in profile_parts if part],
        "mandatory_parts": [part for part in [*profile_parts, thinking, tool_intention_block,
                                                thinking_language_block, grounding] if part],
        "dynamic_parts": [part for part in [context, time_block, weather_block, resume_bundle, diary_block] if part],
        "core_memories": list(core_memories or []),
        "recalled_memories": list(recalled_memories or []),
        "memory_block": _memory_block(list(core_memories or []), list(recalled_memories or [])),
        "has_diary_notifications": bool(diary_block),
    }


async def _build_system_prompt(core_memories: list[dict] | None = None, recalled_memories: list[dict] | None = None, resume_bundle: str = "", *, scene: bool = False) -> str:
    collected = await _collect_system_prompt_parts(
        core_memories=core_memories,
        recalled_memories=recalled_memories,
        resume_bundle=resume_bundle,
        scene=scene,
    )
    profile_count = len(collected["profile_parts"])
    mandatory = collected["mandatory_parts"]
    # Preserve the familiar full-prompt order for non-chat callers and prompt previews.
    leading = mandatory[:profile_count + 1]
    trailing = mandatory[profile_count + 1:]
    return _join_prompt_parts([
        *leading,
        *collected["dynamic_parts"],
        collected["memory_block"],
        *trailing,
    ])

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
            "SELECT id, role, content, thinking, image, display_mode, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
            (conversation_id, limit),
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for r in reversed(rows):
        item = {"id": r["id"], "role": r["role"], "content": r["content"], "created_at": r["created_at"]}
        if r["thinking"]:
            item["thinking"] = r["thinking"]
        if r["image"]:
            item["image_id"] = r["id"]
        item["display_mode"] = r["display_mode"] or "split"
        result.append(item)
    return result

async def search_messages(conversation_id: str, query: str, limit: int = 80) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, role, content, thinking, image, display_mode, created_at
            FROM messages
            WHERE conversation_id = ? AND content LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (conversation_id, like, limit),
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        item = {"id": r["id"], "role": r["role"], "content": r["content"], "created_at": r["created_at"]}
        if r["thinking"]:
            item["thinking"] = r["thinking"]
        if r["image"]:
            item["image_id"] = r["id"]
        item["display_mode"] = r["display_mode"] or "split"
        result.append(item)
    return result


async def get_message_image(message_id: str) -> tuple[bytes, str] | None:
    from app.services.image_storage import InvalidImageError, decode_image, get_image
    result = get_image(message_id)
    if result:
        return result
    async with get_db() as db:
        async with db.execute(
            "SELECT image FROM messages WHERE id = ?", (message_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row or not row["image"] or row["image"] == "file":
        return None
    try:
        return decode_image(row["image"])
    except InvalidImageError:
        return None

async def save_message(conversation_id: str, role: str, content: str, thinking: str = "", image: str = "", display_mode: str = "split") -> str:
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    image_marker = None
    image_saved = False
    if image:
        from app.services.image_storage import save_image
        save_image(msg_id, image)
        image_marker = "file"
        image_saved = True
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, thinking, image, display_mode, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (msg_id, conversation_id, role, content, thinking or None, image_marker, display_mode, now),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            await db.commit()
    except Exception:
        if image_saved:
            from app.services.image_storage import delete_image
            delete_image(msg_id)
        raise
    return msg_id

async def debug_prompt(conversation_id: str, user_message: str) -> dict:
    """调试用：看 Connie 实际收到的完整提示词和召回的记忆。"""
    recalled = await memory_service.recall(user_message, limit=5)
    resume_bundle = await _build_resume_bundle(None)
    system_prompt = await _build_system_prompt(recalled_memories=recalled if recalled else None, resume_bundle=resume_bundle, scene=True)
    return {
        "recalled_memories": recalled,
        "system_prompt_length": len(system_prompt),
        "system_prompt": system_prompt,
    }


def _memory_prompt_line(memory: dict) -> str:
    qualifiers = []
    if memory.get("layer") == "consciousness":
        qualifiers.append("主观感受，非用户确认事实")
    if memory.get("event_date"):
        qualifiers.append(f"事件日期：{memory['event_date']}")
    label = f"（{'；'.join(qualifiers)}）" if qualifiers else ""
    return f"- {label}{memory['content']}"


def _history_timestamp(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    # messages.created_at is stored as UTC when the offset is omitted.
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp


def _build_llm_history_with_time_gaps(history: list[dict]) -> list[dict]:
    result = []
    for i, msg in enumerate(history):
        if i > 0 and msg.get("created_at") and history[i - 1].get("created_at"):
            try:
                prev_time = _history_timestamp(history[i - 1]["created_at"])
                curr_time = _history_timestamp(msg["created_at"])
                gap = curr_time - prev_time
                gap_minutes = gap.total_seconds() / 60
                if gap_minutes >= 30:
                    label = _format_time_gap(gap)
                    result.append({"role": "system", "content": f"（{label}）"})
            except (ValueError, TypeError):
                pass
        if msg.get("created_at"):
            try:
                stamp = _history_timestamp(msg["created_at"]).astimezone(BJ_TZ)
                result.append({"role": "system", "content": f"【下一条消息发送于北京时间 {stamp:%Y-%m-%d %H:%M}；不是事件发生时间】"})
            except (ValueError, TypeError):
                pass
        result.append({"role": msg["role"], "content": msg["content"]})
    return result


def _render_llm_history(history: list[dict], image: str | None = None, user_message: str = "") -> list[dict]:
    rendered = _build_llm_history_with_time_gaps(history)
    if image:
        for message in reversed(rendered):
            if message.get("role") == "user":
                message["content"] = [
                    {"type": "image_url", "image_url": {"url": image}},
                    {"type": "text", "text": user_message},
                ]
                break
    return rendered


def _select_memories_for_budget(core: list[dict], recalled: list[dict], budget: int) -> tuple[list[dict], list[dict]]:
    selected_core = []
    selected_recalled = []
    for target, items in ((selected_core, core), (selected_recalled, recalled)):
        for item in items:
            candidate_core = selected_core + ([item] if target is selected_core else [])
            candidate_recalled = selected_recalled + ([item] if target is selected_recalled else [])
            block = _memory_block(candidate_core, candidate_recalled)
            if context_budget_service.estimate_text_tokens(block) <= budget:
                target.append(item)
    return selected_core, selected_recalled


def _select_blocks_for_budget(parts: list[str], budget: int) -> list[str]:
    selected = []
    for part in parts:
        candidate = _join_prompt_parts([*selected, part])
        if context_budget_service.estimate_text_tokens(candidate) <= budget:
            selected.append(part)
    return selected


def _select_recent_history(
    history: list[dict],
    budget: int,
    *,
    image: str | None = None,
    user_message: str = "",
) -> tuple[list[dict], list[dict]]:
    if not history:
        return [], []
    selected = None
    rendered = None
    for start in range(len(history) - 1, -1, -1):
        candidate = history[start:]
        candidate_rendered = _render_llm_history(candidate, image=image, user_message=user_message)
        if context_budget_service.estimate_messages_tokens(candidate_rendered) > budget:
            break
        selected = candidate
        rendered = candidate_rendered
    if selected is None:
        latest = _render_llm_history(history[-1:], image=image, user_message=user_message)
        required = context_budget_service.estimate_messages_tokens(latest)
        raise context_budget_service.ContextBudgetError(
            "最新一条消息本身超过当前模型可用的输入预算，请缩短消息或调大该槽位的上下文窗口。",
            details={"latest_message_tokens": required, "available_history_tokens": max(0, budget)},
        )
    return selected, rendered


def _build_budgeted_chat_context(
    collected: dict,
    history: list[dict],
    summary: dict | None,
    tools: list[dict],
    slot_settings: dict,
    *,
    image: str | None = None,
    user_message: str = "",
) -> tuple[list[dict], list[dict], dict]:
    context_window = int(slot_settings.get("context_window") or model_settings_service.DEFAULT_CONTEXT_WINDOW)
    output_budget = int(slot_settings.get("output_budget") or model_settings_service.DEFAULT_OUTPUT_BUDGET)
    input_budget = context_budget_service.input_token_budget(context_window, output_budget)

    deduped_core = _deduplicate_core_memories(collected["core_memories"])
    core_memory_block = ""
    if deduped_core:
        core_memory_block = (
            "【核心记忆 · 永远记住】\n"
            + "\n".join(_memory_prompt_line(m) for m in deduped_core)
            + "\n\n（以上核心记忆不会被省略。以她当前明确说明和事件时间为准。自然融入，不逐条播报。未列出的记忆不代表不存在。）"
        )
    mandatory_parts = list(collected["mandatory_parts"])
    if core_memory_block:
        mandatory_parts.append(core_memory_block)
    mandatory_prompt = _join_prompt_parts(mandatory_parts)

    mandatory_tokens = context_budget_service.estimate_messages_tokens([
        {"role": "system", "content": mandatory_prompt}
    ])
    tool_tokens = context_budget_service.estimate_tools_tokens(tools)
    latest_rendered = _render_llm_history(history[-1:], image=image, user_message=user_message)
    latest_tokens = context_budget_service.estimate_messages_tokens(latest_rendered)
    fixed_tokens = mandatory_tokens + tool_tokens + latest_tokens
    if fixed_tokens > input_budget:
        raise context_budget_service.ContextBudgetError(
            "关系档案、核心记忆和最新消息已经超过当前模型的输入预算。系统没有截断这些强制内容；请缩短关系档案或核心记忆，或在模型配置中调大上下文窗口。",
            details={
                "mandatory_tokens": mandatory_tokens,
                "latest_message_tokens": latest_tokens,
                "tool_tokens": tool_tokens,
                "input_budget": input_budget,
                "core_memories_in_mandatory": len(deduped_core),
            },
        )

    extras = input_budget - fixed_tokens
    summary_budget = min(1800, int(extras * 0.22))
    recalled_budget = int(extras * 0.45)
    dynamic_budget = int(extras * 0.20)

    summary_block = ""
    if summary and summary.get("summary"):
        candidate = (
            f"【较早对话滚动摘要 · 覆盖至消息 {summary['through_message_id']}】\n"
            f"{summary['summary']}\n\n"
            "（这是旧对话的压缩索引，不是长期记忆。以当前原话和长期记忆为准，不把摘要中的推断升级成事实。）"
        )
        if context_budget_service.estimate_text_tokens(candidate) <= summary_budget:
            summary_block = candidate

    _, selected_recalled = _select_memories_for_budget(
        [], collected["recalled_memories"], recalled_budget
    )
    recalled_block = ""
    if selected_recalled:
        recalled_block = (
            "【与当前对话相关的记忆】\n"
            + "\n".join(_memory_prompt_line(m) for m in selected_recalled)
            + "\n\n（以上是召回的历史记忆，不保证描述仍适用于现在；意识层是主观感受而非静儿确认的事实。自然融入，不逐条播报；以她当前明确说明和事件时间为准。）"
        )
    if context_budget_service.estimate_text_tokens(recalled_block) > recalled_budget:
        recalled_block = ""

    dynamic_parts = _select_blocks_for_budget(collected["dynamic_parts"], dynamic_budget)
    dynamic_prompt = _join_prompt_parts([
        *dynamic_parts,
        summary_block,
        recalled_block,
    ])
    used_without_history = (
        context_budget_service.estimate_messages_tokens([
            {"role": "system", "content": mandatory_prompt},
            {"role": "system", "content": dynamic_prompt},
        ])
        + tool_tokens
    )
    history_budget = input_budget - used_without_history
    selected_history, llm_history = _select_recent_history(
        history,
        history_budget,
        image=image,
        user_message=user_message,
    )
    messages = [{
        "role": "system",
        "content": mandatory_prompt,
        "cache_control": {"type": "ephemeral"},
    }]
    if dynamic_prompt:
        messages.append({"role": "system", "content": dynamic_prompt})
    messages.extend(llm_history)
    estimated_input = context_budget_service.estimate_messages_tokens(messages) + tool_tokens
    if estimated_input > input_budget:
        raise context_budget_service.ContextBudgetError(
            "组装后的上下文超过当前模型预算，请调大上下文窗口后重试。",
            details={"estimated_input_tokens": estimated_input, "input_budget": input_budget},
        )
    diagnostics = {
        "context_window": context_window,
        "output_budget": output_budget,
        "input_budget": input_budget,
        "estimated_input_tokens": estimated_input,
        "history_messages": len(selected_history),
        "history_omitted": max(0, len(history) - len(selected_history)),
        "core_memories_mandatory": len(deduped_core),
        "core_memories_folded": max(0, len(collected["core_memories"]) - len(deduped_core)),
        "recalled_memories": len(selected_recalled),
        "summary_included": bool(summary_block),
        "stable_prefix_tokens": mandatory_tokens + tool_tokens,
        "prompt_cache_eligible": mandatory_tokens + tool_tokens >= 4096,
    }
    return messages, selected_history, diagnostics


def _assert_context_fits(messages: list[dict], tools: list[dict], input_budget: int) -> None:
    estimated = context_budget_service.estimate_messages_tokens(messages)
    estimated += context_budget_service.estimate_tools_tokens(tools)
    if estimated > input_budget:
        raise context_budget_service.ContextBudgetError(
            "工具调用后的上下文超过当前模型预算，请重试或调大上下文窗口。",
            details={"estimated_input_tokens": estimated, "input_budget": input_budget},
        )


def _bounded_tool_result(messages: list[dict], tools: list[dict], result: str, input_budget: int) -> str:
    used = context_budget_service.estimate_messages_tokens(messages)
    used += context_budget_service.estimate_tools_tokens(tools)
    available = input_budget - used - 12
    if available <= 0:
        raise context_budget_service.ContextBudgetError(
            "工具调用结果没有可用的上下文空间，请重试或调大上下文窗口。",
            details={"input_budget": input_budget, "used_tokens": used},
        )
    return context_budget_service.truncate_text_to_tokens(str(result), available)


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

    from app.services.nudge_service import check_and_close_if_replied
    asyncio.create_task(check_and_close_if_replied(conversation_id))

    model_slot = mode if mode in ("daily", "deep") else "daily"
    config, slot_settings = await model_settings_service.get_model_config_for_slot(model_slot)
    extended_thinking = bool(slot_settings.get("extended_thinking"))
    summary = await context_budget_service.get_conversation_summary(conversation_id)
    through_rowid = int(summary["through_message_rowid"]) if summary else 0
    history = await context_budget_service.get_history_after_summary(
        conversation_id,
        through_message_rowid=through_rowid,
    )

    last_msg_time = None
    for msg in reversed(history):
        if msg["role"] == "assistant":
            last_msg_time = msg.get("created_at")
            break

    core_memories = await memory_service.get_core_memories()
    recalled = await memory_service.recall(user_message, limit=5)
    resume_bundle = await _build_resume_bundle(last_msg_time)
    collected = await _collect_system_prompt_parts(
        core_memories=core_memories,
        recalled_memories=recalled if recalled else None,
        resume_bundle=resume_bundle,
        scene=True,
    )
    tools = select_tools(
        user_message,
        has_diary_notifications=collected["has_diary_notifications"],
        stable=True,
    )
    try:
        messages, selected_history, budget = _build_budgeted_chat_context(
            collected,
            history,
            summary,
            tools,
            slot_settings,
            image=image,
            user_message=user_message,
        )
    except context_budget_service.ContextBudgetError as exc:
        logger.warning("聊天上下文预算不足: %s details=%s", exc, exc.details)
        yield {
            "type": "error",
            "code": "context_budget_exceeded",
            "content": str(exc),
            "details": exc.details,
        }
        return
    logger.info(
        "聊天上下文已组装 slot=%s estimated=%s budget=%s history=%s omitted=%s core=%s recalled=%s summary=%s",
        model_slot,
        budget["estimated_input_tokens"],
        budget["input_budget"],
        budget["history_messages"],
        budget["history_omitted"],
        budget["core_memories"],
        budget["recalled_memories"],
        budget["summary_included"],
    )
    output_budget = budget["output_budget"]
    input_budget = budget["input_budget"]

    try:
        for _ in range(3):
            _assert_context_fits(messages, tools, input_budget)
            assistant_msg = await call_llm_with_tools(
                config,
                messages,
                tools=tools,
                extended_thinking=extended_thinking,
                max_tokens=output_budget,
            )

            tool_calls = assistant_msg.get("tool_calls")
            if not tool_calls:
                break

            tool_names = [tc["function"]["name"] for tc in tool_calls]
            yield {"type": "tool_start", "tools": tool_names, "count": len(tool_calls)}

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
                bounded_result = _bounded_tool_result(messages, tools, result, input_budget)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": bounded_result,
                })

            yield {"type": "tool_done", "tools": tool_names, "count": len(tool_calls)}
        else:
            _assert_context_fits(messages, tools, input_budget)
            assistant_msg = await call_llm_with_tools(
                config,
                messages,
                extended_thinking=extended_thinking,
                max_tokens=output_budget,
            )
    except context_budget_service.ContextBudgetError as e:
        logger.warning("工具调用后上下文预算不足: %s details=%s", e, e.details)
        yield {"type": "error", "code": "context_budget_exceeded", "content": str(e), "details": e.details}
        return
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
                max_tokens=output_budget,
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
    asyncio.create_task(_push_reply_bg(full_reply, reply_style))
    asyncio.create_task(_compact_conversation_bg(conversation_id))


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


async def _compact_conversation_bg(conversation_id: str):
    try:
        await context_budget_service.maybe_compact_conversation(conversation_id)
    except Exception as e:
        logger.warning("滚动摘要更新失败: %s", e)


async def _push_reply_bg(reply: str, reply_style: str = "split"):
    try:
        from app.services.push_service import send_push
        import asyncio as _aio
        if reply_style == "split":
            parts = [p.strip() for p in reply.split("\n\n") if p.strip()]
            if not parts:
                parts = [reply]
            for i, part in enumerate(parts):
                await send_push(body=part[:120], tag=f"chat-{i}")
                if i < len(parts) - 1:
                    delay = max(0.8 + len(part) * 0.03, 1.0)
                    await _aio.sleep(delay)
        else:
            await send_push(body=reply[:120], tag="chat")
    except Exception as e:
        logger.warning("聊天推送失败: %s", e)
