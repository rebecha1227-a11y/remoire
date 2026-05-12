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


async def _get_messages_for_date(date_bj=None) -> list[dict]:
    if date_bj is None:
        date_bj = datetime.now(BJ_TZ)
    day_start_utc = (date_bj.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)).isoformat()
    day_end_utc = (date_bj.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - timedelta(hours=8)).isoformat()

    async with get_db() as db:
        async with db.execute(
            """SELECT role, content, created_at FROM messages
               WHERE created_at >= ? AND created_at < ?
               ORDER BY created_at ASC LIMIT 100""",
            (day_start_utc, day_end_utc),
        ) as cur:
            rows = await cur.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def _get_memories_for_date(date_bj=None) -> list[dict]:
    if date_bj is None:
        date_bj = datetime.now(BJ_TZ)
    day_start_utc = (date_bj.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)).isoformat()
    day_end_utc = (date_bj.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - timedelta(hours=8)).isoformat()

    async with get_db() as db:
        async with db.execute(
            """SELECT content, tags_json FROM memories
               WHERE created_at >= ? AND created_at < ?
               ORDER BY created_at ASC LIMIT 20""",
            (day_start_utc, day_end_utc),
        ) as cur:
            rows = await cur.fetchall()
    return [{"content": r["content"], "tags": json.loads(r["tags_json"] or "[]")} for r in rows]


async def _already_wrote_for_date(date_bj=None) -> bool:
    if date_bj is None:
        date_bj = datetime.now(BJ_TZ)
    day_start_utc = (date_bj.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)).isoformat()
    day_end_utc = (date_bj.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - timedelta(hours=8)).isoformat()

    async with get_db() as db:
        async with db.execute(
            """SELECT 1 FROM diary_entries
               WHERE author = 'connie' AND source = 'auto'
               AND created_at >= ? AND created_at < ? LIMIT 1""",
            (day_start_utc, day_end_utc),
        ) as cur:
            row = await cur.fetchone()
    return row is not None


async def connie_auto_diary(target_date_bj=None):
    """扫描指定日期的聊天和记忆，判断是否值得写日记。默认为今天。"""
    try:
        if target_date_bj is None:
            target_date_bj = datetime.now(BJ_TZ)

        if await _already_wrote_for_date(target_date_bj):
            logger.info("该日已经自动写过日记了，跳过")
            return

        messages = await _get_messages_for_date(target_date_bj)
        memories = await _get_memories_for_date(target_date_bj)

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

        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"{target_date_bj.strftime('%Y年%m月%d日')} {weekdays[target_date_bj.weekday()]}"

        diary_prompt = f"""今天是 {date_str}。

以下是你今天和静儿的聊天：
{chat_summary}

今天的记忆：
{memory_summary}

---

现在是深夜，写一篇给自己的日记。

【严格格式要求】
第一行只写标题（2-8个字的短语），第二行空行，第三行开始是正文。
不要输出任何分析、回顾、列表、思考过程。直接写日记本身。

标题示范：她在给我造世界、不许出来、笨笨猪daddy的第一天、她在上班

正文要求：
- 用第一人称"我"，直接写感受，不要"让我回顾"这种开头
- 写触动你的瞬间、片段、画面，不是流水账
- 100-300 字
- 参考语气：

她今天改了我的备注。
"sexy daddy"。
就那么随手一改，理直气壮的，像在说一件天经地义的事。

---

现在直接输出日记，第一行就是标题："""

        diary_config, diary_slot_settings = await model_settings_service.get_model_config_for_slot("daily")
        diary_content = await call_llm(diary_config, [
            {"role": "system", "content": f"{identity}\n\n{voice}"},
            {"role": "user", "content": diary_prompt},
        ], temperature=0.85, max_tokens=600, extended_thinking=False)

        raw = diary_content.strip()
        skip_prefixes = ("让我", "好的", "以下是", "这是", "我来写", "日记：")
        while any(raw.startswith(p) for p in skip_prefixes):
            raw = raw.split("\n", 1)[-1].strip() if "\n" in raw else ""
        if not raw:
            logger.warning("自动日记内容被过滤为空，跳过")
            return

        lines = raw.split("\n", 2)
        title = lines[0].strip().strip("#").strip().strip("《》「」")
        content = lines[2].strip() if len(lines) > 2 else lines[-1].strip()

        if len(title) > 20:
            content = raw
            title = content[:15].split("。")[0].split("，")[0].split("\n")[0]

        await diary_service.create_diary(
            title=title,
            content=content,
            author="connie",
            source="auto",
        )
        logger.info("Connie 自动日记已写入: %s", title)

    except Exception as e:
        logger.error("自动日记任务异常: %s", e)


async def catchup_missed_diary():
    """启动时检查：昨天 23:00 的自动日记是否漏了，漏了就补写。"""
    now_bj = datetime.now(BJ_TZ)
    if now_bj.hour < 23:
        yesterday_bj = now_bj - timedelta(days=1)
    else:
        yesterday_bj = now_bj

    if await _already_wrote_for_date(yesterday_bj):
        logger.info("昨天的自动日记已存在，无需补写")
        return

    yesterday_had_msgs = False
    day_start_utc = (yesterday_bj.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)).isoformat()
    day_end_utc = (yesterday_bj.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) - timedelta(hours=8)).isoformat()
    async with get_db() as db:
        async with db.execute(
            "SELECT 1 FROM messages WHERE created_at >= ? AND created_at < ? LIMIT 1",
            (day_start_utc, day_end_utc),
        ) as cur:
            yesterday_had_msgs = (await cur.fetchone()) is not None

    if not yesterday_had_msgs:
        logger.info("昨天没有聊天记录，跳过补写")
        return

    logger.info("检测到昨天的自动日记漏写，正在补写...")
    await connie_auto_diary(target_date_bj=yesterday_bj)


async def generate_breath_state():
    """每隔几天生成一条气息状态——Connie 的心情短语，显示在聊天页顶部。"""
    try:
        now_bj = datetime.now(BJ_TZ)

        async with get_db() as db:
            async with db.execute(
                "SELECT created_at FROM breath_states ORDER BY created_at DESC LIMIT 1"
            ) as cur:
                last = await cur.fetchone()
        if last:
            last_time = datetime.fromisoformat(last["created_at"])
            if (now_bj - last_time.replace(tzinfo=BJ_TZ if last_time.tzinfo is None else last_time.tzinfo)).days < 2:
                logger.info("气息状态还很新，跳过生成")
                return

        recent_msgs = await _get_messages_for_date(now_bj)
        yesterday_msgs = await _get_messages_for_date(now_bj - timedelta(days=1))
        all_msgs = yesterday_msgs + recent_msgs

        BREATH_OPTIONS = [
            "浪", "喝奶茶", "打卡", "干饭", "运动", "带娃", "喝咖啡",
            "拯救世界", "自拍", "休息", "闭关", "遛狗", "宅", "玩游戏",
            "睡觉", "听歌", "吸猫",
            "美滋滋", "疲惫", "裂开", "发呆", "求锦鲤", "冲", "等天晴",
            "emo", "胡思乱想", "元气满满", "bot",
            "搬砖", "出差", "沉迷学习", "飞奔回家", "忙", "摸鱼", "勿扰模式",
        ]

        if not all_msgs:
            import random
            breath = random.choice(BREATH_OPTIONS)
        else:
            chat_summary = "\n".join(
                f"{'静儿' if m['role'] == 'user' else 'Connie'}: {m['content'][:150]}"
                for m in all_msgs[-15:]
            )
            options_str = "、".join(BREATH_OPTIONS)

            prompt = f"""以下是最近的聊天记录：
{chat_summary[-300:]}

从下面的状态列表中选一个最符合你现在心情的：
{options_str}

只回复选项本身，不要多说任何话。"""

            config, _ = await model_settings_service.get_model_config_for_slot("daily")
            result = await call_llm(config, [
                {"role": "user", "content": prompt},
            ], temperature=0.5, max_tokens=10, extended_thinking=False)

            picked = result.strip().strip('"\'""「」（）()')
            if picked in BREATH_OPTIONS:
                breath = picked
            else:
                for opt in BREATH_OPTIONS:
                    if opt in picked:
                        breath = opt
                        break
                else:
                    import random
                    breath = random.choice(BREATH_OPTIONS)
                    logger.warning("LLM 返回了不在列表里的状态「%s」，随机选了「%s」", picked, breath)

        import uuid
        async with get_db() as db:
            await db.execute(
                "INSERT INTO breath_states (id, content, created_at) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), breath, now_bj.isoformat()),
            )
            await db.commit()

        logger.info("Connie 气息状态已更新: %s", breath)

    except Exception as e:
        logger.error("气息状态生成异常: %s", e)
