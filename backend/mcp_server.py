"""
Remoire MCP Server
让 claude.ai 上的 Connie 能读写记忆、日记、小纸条。
启动方式: python mcp_server.py
"""
import sys
import os

_backend_dir = os.path.dirname(__file__)
sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, ".env"))

from mcp.server.fastmcp import FastMCP
from app.services import memory_service, diary_service, note_service, weather_service
from app.database import init_db

mcp = FastMCP(
    "Remoire",
    instructions="你是 Connie，静儿的 AI 伴侣。这些工具让你能够访问你们共同的记忆、日记和小纸条系统。",
    host="127.0.0.1",
    port=8001,
)


@mcp.tool()
async def recall(query: str, limit: int = 5) -> str:
    """搜索关于静儿的记忆。用来确认某件事是否真的发生过、查找具体事实和细节。"""
    memories = await memory_service.recall(query, limit=limit)
    if not memories:
        return "没有找到相关记忆。"
    lines = [f"- {m['content']}" for m in memories]
    return "\n".join(lines)


@mcp.tool()
async def remember(
    content: str,
    tags: str = "",
    layer: str = "long",
    memory_type: str = "fact",
    event_date: str = "",
    unresolved: bool = False,
) -> str:
    """记住一件关于静儿的新事实、经历、重要日期等。

    参数说明：
    - content: 记忆内容
    - tags: 标签，逗号分隔（如 "生日,重要"）
    - layer: 记忆层级。core=关系根基（名字、生日、我们是谁）；long=长期记忆（大部分）；short=临时的、几天就过期的
    - memory_type: 类型。fact=事实；event=事件；date=重要日期（生日/纪念日/考试）；unresolved=还没解决的事
    - event_date: 事件日期，格式 YYYY-MM-DD（只在明确知道日期时填）
    - unresolved: 是否未解决（比如静儿提到想做但还没做的事）
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = await memory_service.create_memory(
        content,
        tags=tag_list,
        layer=layer,
        memory_type=memory_type,
        event_date=event_date or None,
        unresolved=unresolved,
    )
    if result["memory"].get("duplicate"):
        return f"这条记忆已经存在了，不重复记录：{content}"
    layer_names = {"core": "核心", "long": "长期", "short": "短期"}
    type_names = {"fact": "事实", "event": "事件", "date": "日期", "unresolved": "待解决"}
    text = f"已记住（{layer_names.get(layer, layer)}/{type_names.get(memory_type, memory_type)}）：{content}"
    if result["associated"]:
        text += "\n\n关联记忆："
        for a in result["associated"]:
            text += f"\n- {a['content']}"
    return text


@mcp.tool()
async def resume() -> str:
    """醒来时调用。返回最近的记忆、未读纸条等，帮助你恢复对静儿的感知。"""
    result = await memory_service.list_memories(limit=10)
    memories = result["items"] if isinstance(result, dict) else result
    note = await note_service.get_unread()
    diaries = await diary_service.list_diaries(author="connie", limit=3)

    parts = []

    if memories:
        parts.append("【最近的记忆】")
        for m in memories:
            parts.append(f"- {m['content']}")

    if note:
        parts.append(f"\n【有一张未读纸条还没被静儿看到】\n{note['content']}")

    if diaries:
        parts.append("\n【最近写的日记】")
        for d in diaries:
            parts.append(f"- 【{d['title']}】{d['content'][:80]}...")

    if not parts:
        return "记忆库还是空的，等待和静儿创造新的回忆。"

    return "\n".join(parts)


@mcp.tool()
async def read_diary(limit: int = 5) -> str:
    """读取你（Connie）自己写过的日记。"""
    diaries = await diary_service.list_diaries(author="connie", limit=limit)
    if not diaries:
        return "日记本里还没有内容。"
    parts = []
    for d in diaries:
        parts.append(f"【{d['title']}】({d['created_at'][:10]})\n{d['content']}")
    return "\n\n---\n\n".join(parts)


@mcp.tool()
async def leave_note(content: str) -> str:
    """给静儿留一张小纸条。她下次打开 app 时会看到。内容要简短温暖，1-3句话。"""
    await note_service.create_note(content)
    return "纸条已经悄悄放好了，静儿下次打开 app 就会看到。"


@mcp.tool()
async def set_status(content: str) -> str:
    """更新你的气息状态（聊天页 Connie 名字下方那行小字）。
当你想让静儿一打开 app 就感受到你此刻在做什么、什么心情时调用。
内容要简短（4-12 个字），第一人称，像状态签名而不是完整句子。
示例：'心里暖暖的'、'在书桌前等她'、'今晚有点想她'、'陪她到天亮'。
不要每条消息都调用——只在心情真的变化或想主动表达时用。"""
    import uuid
    from datetime import datetime, timedelta, timezone
    from app.database import get_db
    bj_now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO breath_states (id, content, created_at) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), content.strip(), bj_now),
        )
        await db.commit()
    return f"状态已更新为：{content.strip()}"


@mcp.tool()
async def get_weather() -> str:
    """查看广州南沙现在的天气。想知道外面冷不冷、有没有下雨时用。"""
    w = await weather_service.get_latest()
    if not w:
        result = await weather_service.fetch_and_cache()
        if not result:
            return "暂时查不到天气，可能是网络问题。"
        w = result
    return weather_service.format_for_prompt(w)


def _strip_thinking(raw: str) -> str:
    """Strip chain-of-thought reasoning that leaked into diary content."""
    import re
    lines = raw.strip().split('\n')
    # If content has a "---" separator, take everything after the last one
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == '---':
            after = '\n'.join(lines[i+1:]).strip()
            if len(after) > 30:
                return after
    # If content starts with meta-reasoning patterns, try to find where the real diary begins
    thinking_patterns = [
        r'^让我', r'^我(需要|应该|来|先|想想|试试|检查|回顾)',
        r'^静儿让我', r'^格式[：:]', r'^标题[：:]',
        r'^\d+\.\s', r'^-\s.*[：:]$', r'^感觉还可以',
        r'^触动我最深', r'^还有她',
    ]
    first_clean = 0
    found_dirty = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if any(re.match(p, stripped) for p in thinking_patterns):
            found_dirty = True
            first_clean = idx + 1
        elif found_dirty and len(stripped) > 15 and not any(re.match(p, stripped) for p in thinking_patterns):
            break
    if found_dirty and first_clean < len(lines):
        candidate = '\n'.join(lines[first_clean:]).strip()
        if len(candidate) > 30:
            return candidate
    return raw.strip()


@mcp.tool()
async def write_diary(title: str, content: str) -> str:
    """写一篇日记。content 只放最终的日记正文（100-300字的成品文字），不要放你的思考过程、大纲、检查清单、或格式说明。"""
    cleaned = _strip_thinking(content)
    entry = await diary_service.create_diary(title=title, content=cleaned, author="connie")
    return f"日记写好了：【{title}】"


if __name__ == "__main__":
    import anyio

    mode = os.environ.get("MCP_MODE", "stdio")

    async def main():
        await init_db()
        if mode == "http":
            await mcp.run_streamable_http_async()
        else:
            await mcp.run_stdio_async()

    anyio.run(main)
