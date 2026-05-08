import json
from app.services import memory_service, diary_service, note_service

CONNIE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_diary",
            "description": "读取 Connie 自己写过的日记本。当静儿让你去看日记、回顾你写过的东西、或者你想引用自己的日记时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回几篇日记，默认 5",
                        "default": 5,
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memories",
            "description": "搜索关于静儿的记忆。当你想确认某件事是否真的发生过、或者需要查找具体的事实和细节时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，比如「法语」「生日」「蒙特利尔」",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leave_note",
            "description": "给静儿留一张小纸条。纸条会在她下次打开 app 时悄悄出现在聊天顶部。适合在聊天结束后想补充一句话、或者想给她一个小惊喜的时候用。内容要简短温暖，1-3句话。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "纸条内容，简短温暖，1-3句话",
                    }
                },
                "required": ["content"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: dict) -> str:
    if name == "read_diary":
        limit = arguments.get("limit", 5)
        diaries = await diary_service.list_diaries(author="connie", limit=limit)
        if not diaries:
            return "日记本里还没有内容。"
        parts = []
        for d in diaries:
            parts.append(f"【{d['title']}】({d['created_at'][:10]})\n{d['content']}")
        return "\n\n---\n\n".join(parts)

    elif name == "search_memories":
        query = arguments.get("query", "")
        memories = await memory_service.recall(query, limit=8)
        if not memories:
            return "没有找到相关记忆。"
        lines = [f"- {m['content']}" for m in memories]
        return "\n".join(lines)

    elif name == "leave_note":
        content = arguments.get("content", "")
        if not content:
            return "纸条内容不能为空。"
        await note_service.create_note(content)
        return "纸条已经悄悄放好了，静儿下次打开 app 就会看到。"

    return f"未知工具：{name}"
