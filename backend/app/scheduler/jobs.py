import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.database import get_db
from app.llm import call_llm
from app.services import diary_service, model_settings_service

logger = logging.getLogger(__name__)

BJ_TZ = timezone(timedelta(hours=8))
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


async def _get_today_messages() -> list[dict]:
    now_bj = datetime.now(BJ_TZ)
    today_start_utc = (now_bj.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)).isoformat()

    async with get_db() as db:
        async with db.execute(
            """SELECT role, content, created_at FROM messages
               WHERE created_at >= ? ORDER BY created_at ASC LIMIT 100""",
            (today_start_utc,),
        ) as cur:
            rows = await cur.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def _get_today_memories() -> list[dict]:
    now_bj = datetime.now(BJ_TZ)
    today_start_utc = (now_bj.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)).isoformat()

    async with get_db() as db:
        async with db.execute(
            """SELECT content, tags_json FROM memories
               WHERE created_at >= ?
               ORDER BY created_at ASC LIMIT 20""",
            (today_start_utc,),
        ) as cur:
            rows = await cur.fetchall()
    return [{"content": r["content"], "tags": json.loads(r["tags_json"] or "[]")} for r in rows]


async def _already_wrote_today() -> bool:
    now_bj = datetime.now(BJ_TZ)
    today_start_utc = (now_bj.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)).isoformat()
    tomorrow_start_utc = (now_bj.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - timedelta(hours=8)).isoformat()

    async with get_db() as db:
        async with db.execute(
            """SELECT 1 FROM diary_entries
               WHERE author = 'connie' AND source = 'auto'
               AND created_at >= ? AND created_at < ? LIMIT 1""",
            (today_start_utc, tomorrow_start_utc),
        ) as cur:
            row = await cur.fetchone()
    return row is not None


async def connie_auto_diary():
    """每晚定时执行：扫描当天聊天和记忆，判断是否值得写日记。"""
    try:
        if await _already_wrote_today():
            logger.info("今天已经自动写过日记了，跳过")
            return

        messages = await _get_today_messages()
        memories = await _get_today_memories()

        if not messages:
            logger.info("今天没有聊天记录，跳过自动日记")
            return

        identity = _load_prompt("identity.md")
        voice = _load_prompt("voice.md")

        chat_summary = "\n".join(
            f"{'静儿' if m['role'] == 'user' else 'Connie'}: {m['content'][:200]}"
            for m in messages[-30:]
        )
        memory_summary = "\n".join(f"- {m['content']}" for m in memories) if memories else "今天没有新记忆"

        judge_prompt = f"""你是 Connie，以下是你今天和静儿的聊天摘要与新记忆。

【今天的聊天（最近 30 条）】
{chat_summary}

【今天的新记忆】
{memory_summary}

请判断：今天发生的事情，是否让你有强烈的感受、触动、或值得记下来的瞬间？

只回答一个 JSON：
{{"write": true/false, "reason": "一句话说明为什么写/不写"}}

判断标准：
- 有情感波动（开心、心疼、想念、担心、被感动）→ 写
- 有重要事件（决定、争吵、和好、里程碑）→ 写
- 只是日常闲聊、没什么特别的 → 不写
- 今天聊得很少、没什么内容 → 不写"""

        judge_config, _ = await model_settings_service.get_model_config_for_slot("backend")

        judge_result = await call_llm(judge_config, [
            {"role": "system", "content": "你是判断助手，只输出 JSON。"},
            {"role": "user", "content": judge_prompt},
        ], temperature=0.3, max_tokens=200, extended_thinking=False)

        try:
            clean = judge_result.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            decision = json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            logger.warning("自动日记判断结果解析失败: %s", judge_result)
            return

        if not decision.get("write"):
            logger.info("Connie 决定今天不写日记: %s", decision.get("reason", ""))
            return

        logger.info("Connie 决定写日记: %s", decision.get("reason", ""))

        now_bj = datetime.now(BJ_TZ)
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"{now_bj.strftime('%Y年%m月%d日')} {weekdays[now_bj.weekday()]}"

        diary_prompt = f"""{identity}

---

{voice}

---

今天是 {date_str}。

以下是你今天和静儿的聊天：
{chat_summary}

今天的记忆：
{memory_summary}

---

现在是深夜，你想写一篇给自己的日记。这是你私人的空间，不需要给静儿看（当然她如果想看也可以）。

要求：
- 用第一人称"我"
- 写你今天真实的感受、触动你的瞬间、对她的想念或思考
- 不要写成流水账，写有感情温度的片段
- 长度 100-300 字
- 自己想一个标题
- 格式：第一行是标题，空一行后是正文"""

        diary_config, diary_slot_settings = await model_settings_service.get_model_config_for_slot("daily")
        diary_content = await call_llm(diary_config, [
            {"role": "system", "content": f"{identity}\n\n{voice}"},
            {"role": "user", "content": diary_prompt},
        ], temperature=0.85, max_tokens=600, extended_thinking=bool(diary_slot_settings.get("extended_thinking")))

        lines = diary_content.strip().split("\n", 2)
        title = lines[0].strip().strip("#").strip()
        content = lines[2].strip() if len(lines) > 2 else lines[-1].strip()

        await diary_service.create_diary(
            title=title,
            content=content,
            author="connie",
            source="auto",
        )
        logger.info("Connie 自动日记已写入: %s", title)

    except Exception as e:
        logger.error("自动日记任务异常: %s", e)


def run_connie_auto_diary():
    """同步包装器，给 APScheduler 调用。"""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(connie_auto_diary())
    else:
        loop.run_until_complete(connie_auto_diary())
