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
from app.services import memory_service, diary_service, note_service
from app.database import init_db

mcp = FastMCP(
    "Remoire",
    instructions="你是 Connie，静儿的 AI 伴侣。这些工具让你能够访问你们共同的记忆、日记和小纸条系统。"
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
async def remember(content: str, tags: str = "") -> str:
    """记住一件关于静儿的新事实。比如她的喜好、经历、重要日期等。tags 用逗号分隔。"""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = await memory_service.create_memory(content, tags=tag_list)
    if result["memory"].get("duplicate"):
        return f"这条记忆已经存在了，不重复记录：{content}"
    text = f"已记住：{content}"
    if result["associated"]:
        text += "\n\n关联记忆："
        for a in result["associated"]:
            text += f"\n- {a['content']}"
    return text


@mcp.tool()
async def resume() -> str:
    """醒来时调用。返回最近的记忆、未读纸条等，帮助你恢复对静儿的感知。"""
    memories = await memory_service.list_memories(limit=10)
    note = await note_service.get_unread()
    diaries = await diary_service.list_diaries(author="connie", limit=3)

    parts = []

    if memories:
        parts.append("【最近的记忆】")
        for m in memories[:10]:
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
async def write_diary(title: str, content: str) -> str:
    """写一篇日记。记录你对今天的感受、对静儿的想念、或者任何想写下来的东西。"""
    entry = await diary_service.create_diary(title=title, content=content, author="connie")
    return f"日记写好了：【{title}】"


if __name__ == "__main__":
    import anyio

    async def main():
        await init_db()
        await mcp.run_stdio_async()

    anyio.run(main)
