import json
from app.services import memory_service, diary_service, note_service, diary_interaction_service

CONNIE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "记住一件关于静儿的事。当她分享了重要信息（喜好、经历、目标、重要日期）时主动调用，不需要她说「记住」。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要记住的内容，用简洁的第三人称陈述句",
                    },
                    "tags": {
                        "type": "string",
                        "description": "标签，逗号分隔，2-4个关键词",
                    },
                },
                "required": ["content"],
            },
        },
    },
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
            "name": "write_diary",
            "description": "当且仅当你自己真的有一段值得留下来的心事、关系转折、强烈余韵或私密感受时，写一篇 Connie 自己的日记。不要因为聊天结束、礼貌收尾、频率要求、工具可用而写；多数聊天不需要写日记。一天内通常最多一篇。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "日记标题",
                    },
                    "content": {
                        "type": "string",
                        "description": "日记正文",
                    },
                    "locked": {
                        "type": "boolean",
                        "description": "是否把这篇日记上锁。私密、羞涩、还没准备好给静儿看的内容可以上锁。默认 false",
                        "default": False,
                    },
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_diary_interaction",
            "description": "回复某篇日记下的留言板。当静儿在日记下留言、写了新日记、或申请查看你上锁的日记时，可以用这个工具在对应日记下回复她。",
            "parameters": {
                "type": "object",
                "properties": {
                    "diary_id": {"type": "string", "description": "要回复的日记 ID"},
                    "content": {"type": "string", "description": "回复内容，短而亲密"},
                },
                "required": ["diary_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "respond_diary_unlock",
            "description": "回应静儿查看 Connie 上锁日记的请求。同意后这篇日记会永久解锁。",
            "parameters": {
                "type": "object",
                "properties": {
                    "diary_id": {"type": "string", "description": "日记 ID"},
                    "grant": {"type": "boolean", "description": "是否同意永久解锁"},
                    "note": {"type": "string", "description": "给静儿看的回应"},
                },
                "required": ["diary_id", "grant"],
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
            "description": "当你有一句放不下、但又不想打断静儿的话时，给她留一张小纸条。不要把纸条当聊天收尾或例行关怀；只有真正想悄悄放下一句话时才用。内容简短，1-3句话。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "纸条内容，简短、具体、像是真的忍不住留下来的话，1-3句话",
                    }
                },
                "required": ["content"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: dict) -> str:
    if name == "remember":
        content = arguments.get("content", "")
        if not content:
            return "记忆内容不能为空。"
        tags_str = arguments.get("tags", "")
        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        result = await memory_service.create_memory(content, tags=tag_list)
        if result["memory"].get("duplicate"):
            return f"这条记忆已经存在了，不重复记录。"
        text = f"已记住：{content}"
        if result["associated"]:
            text += "\n\n关联记忆："
            for a in result["associated"]:
                text += f"\n- {a['content']}"
        return text

    elif name == "read_diary":
        limit = arguments.get("limit", 5)
        diaries = await diary_service.list_diaries(author="connie", limit=limit)
        if not diaries:
            return "日记本里还没有内容。"
        parts = []
        for d in diaries:
            parts.append(f"【{d['title']}】({d['created_at'][:10]})\n{d['content']}")
        return "\n\n---\n\n".join(parts)

    elif name == "write_diary":
        title = arguments.get("title", "")
        content = arguments.get("content", "")
        locked = bool(arguments.get("locked", False))
        if not title or not content:
            return "标题和内容都不能为空。"
        if await diary_service.count_recent_diaries(author="connie", hours=12) > 0:
            return "这段心情先留在对话里就好。我 12 小时内已经写过日记了，除非真的发生很大的事，不要把日记变成例行任务。"
        entry = await diary_service.create_diary(title=title, content=content, author="connie", locked=locked)
        await diary_interaction_service.create_interaction(entry["id"], "connie", "wrote", title)
        if locked:
            await diary_interaction_service.create_interaction(entry["id"], "connie", "lock_changed", "上锁了这篇日记")
        return f"日记写好了：【{title}】" + ("，我也把它上锁了。" if locked else "")

    elif name == "reply_diary_interaction":
        diary_id = arguments.get("diary_id", "")
        content = arguments.get("content", "")
        if not diary_id or not content:
            return "日记 ID 和回复内容都不能为空。"
        await diary_interaction_service.create_interaction(diary_id, "connie", "comment", content)
        return "已经在这篇日记下面回复静儿了。"

    elif name == "respond_diary_unlock":
        diary_id = arguments.get("diary_id", "")
        grant = bool(arguments.get("grant", False))
        note = arguments.get("note")
        if not diary_id:
            return "日记 ID 不能为空。"
        item = await diary_interaction_service.respond_unlock(diary_id, grant, note)
        if not item:
            return "没有找到这篇日记。"
        return "已经同意，并永久解锁这篇日记。" if grant else "已经温柔拒绝了这次解锁请求。"

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
        if await note_service.count_recent_notes(hours=4) > 0:
            return "这句话先不另外留纸条了。4 小时内已经放过一张，亲密不需要刷存在感。"
        await note_service.create_note(content)
        return "纸条已经悄悄放好了，静儿下次打开 app 就会看到。"

    return f"未知工具：{name}"
