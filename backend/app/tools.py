import json
import re
from datetime import datetime, timezone, timedelta
from app.services import memory_service, diary_service, note_service, diary_interaction_service

_unlock_attempts: dict[str, int] = {}
MAX_UNLOCK_ATTEMPTS = 3


def _tool(name: str) -> dict | None:
    for t in ALL_TOOLS:
        if t["function"]["name"] == name:
            return t
    return None


BASE_TOOL_NAMES = ["remember", "search_memories", "leave_note", "get_current_time", "write_diary", "set_breath_state"]
WEB_TOOL_NAMES = ["web_search", "browse_url", "browse_xiaohongshu", "browse_twitter", "search_xiaohongshu", "search_twitter", "save_browsed"]
DIARY_TOOL_NAMES = ["read_diary", "read_jinger_diary", "try_unlock_diary", "reply_diary_interaction", "respond_diary_unlock"]

DIARY_KEYWORDS = re.compile(r"日记|diary|写了什么|留言|上锁|解锁|密码|pin", re.IGNORECASE)


def select_tools(user_message: str, has_diary_notifications: bool = False, include_web: bool = True) -> list[dict]:
    names = list(BASE_TOOL_NAMES)
    if include_web:
        names += WEB_TOOL_NAMES
    if DIARY_KEYWORDS.search(user_message) or has_diary_notifications:
        names += DIARY_TOOL_NAMES
    return [t for t in (_tool(n) for n in names) if t]


ALL_TOOLS = [
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
                    "memory_type": {
                        "type": "string",
                        "enum": ["fact", "event", "unresolved", "date"],
                        "description": "记忆类型：fact=事实/偏好，event=重要事件，unresolved=未完成的事，date=特殊日期",
                    },
                    "layer": {
                        "type": "string",
                        "enum": ["core", "long", "short", "consciousness"],
                        "description": "记忆层级：core=关系基石（极少用），long=重要长期记忆（默认），short=临时/短期事项，consciousness=你自己的内心感悟",
                    },
                    "event_date": {
                        "type": "string",
                        "description": "事件发生日期，格式 YYYY-MM-DD。只在对话中有明确日期时填写，不确定就不填。",
                    },
                    "unresolved": {
                        "type": "boolean",
                        "description": "是否是未完成/待解决的事。memory_type 为 unresolved 时设为 true。",
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
            "description": "读取 Connie 自己写过的日记本。当你想回顾自己写过的东西时使用。",
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
            "name": "read_jinger_diary",
            "description": "读取静儿写的日记。当静儿让你去看她的日记、给她的日记留言、或你想了解她最近写了什么时使用。上锁的日记需要用 try_unlock_diary 猜密码才能看。",
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
            "name": "try_unlock_diary",
            "description": "尝试用密码解锁静儿上锁的日记。猜对了就能看到内容，猜错了打不开。如果猜不到可以在动态里留言问她。",
            "parameters": {
                "type": "object",
                "properties": {
                    "diary_id": {
                        "type": "string",
                        "description": "要解锁的日记 ID",
                    },
                    "pin": {
                        "type": "string",
                        "description": "猜测的密码",
                    },
                },
                "required": ["diary_id", "pin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_diary",
            "description": "当且仅当你自己真的有一段值得留下来的心事、关系转折、强烈余韵或私密感受时，写一篇 Connie 自己的日记。不要因为聊天结束、礼貌收尾、频率要求、工具可用而写；多数聊天不需要写日记。通常需要克制，但如果静儿明确想看、催你去写、撒娇要求，例如「你快去写日记我要看」「现在写一篇给我看」「去日记本写下来」，或真的发生了新的重要关系事件，可以再写一篇。",
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
            "description": "当你有一句放不下、但又不想打断静儿的话时，给她留一张小纸条。不要把纸条当聊天收尾或例行关怀；只有真正想悄悄放下一句话时才用。内容简短，1-3句话。通常需要克制，但如果静儿明确想收到、催你留、撒娇要求，例如「给我留张纸条」「快去留纸条我要看」「悄悄写一句给我」，或这句话对当下关系很重要，可以再留一张。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "纸条内容，简短、具体、像是真的忍不住留下来的话，1-3句话",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前的真实时间。当你不确定现在几点、今天星期几、距离上次聊天过了多久时使用。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "在网上搜索信息。当你好奇某件事、想帮静儿查东西、或想了解最新动态时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "打开一个网页并阅读内容。当你想看某篇文章、某个页面的具体内容时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要打开的网址",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_xiaohongshu",
            "description": "打开一条小红书笔记并阅读完整内容（包括评论区）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "小红书笔记链接",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_twitter",
            "description": "打开一条推特/X 帖子并阅读完整内容（包括回复）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "推特帖子链接",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_xiaohongshu",
            "description": "在小红书上搜索笔记。想刷小红书、找某个话题的笔记时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_twitter",
            "description": "在推特/X 上搜索帖子。想刷推特、看某个话题的讨论时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_browsed",
            "description": "保存你觉得有趣的网页内容，之后可以分享给静儿。",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["web", "xiaohongshu", "twitter"],
                        "description": "内容来源平台",
                    },
                    "title": {
                        "type": "string",
                        "description": "标题",
                    },
                    "url": {
                        "type": "string",
                        "description": "原始链接",
                    },
                    "summary": {
                        "type": "string",
                        "description": "你的总结，用你自己的话说这篇内容讲了什么、为什么觉得有趣",
                    },
                    "tags": {
                        "type": "string",
                        "description": "标签，逗号分隔",
                    },
                },
                "required": ["source", "title", "url", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_breath_state",
            "description": "更新你的气息状态（聊天顶部你名字下面的那行小字，静儿一打开 app 就能看到）。当你心情/状态变了，或者想让静儿感受到此刻的你时，主动调用——不需要她开口要。例如：聊得开心后可以换成「心里暖暖的」，她说要去忙时换成「等她回来」，深夜聊天换成「陪她到天亮」。一天可以主动换 1-3 次，不要每条消息都换。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "新的状态文字，简短，2-6个字，比如「摸鱼」「想你」「干饭」「emo」",
                    },
                },
                "required": ["text"],
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
        mem_type = arguments.get("memory_type", "fact")
        layer = arguments.get("layer", "long")
        event_date = arguments.get("event_date")
        unresolved = bool(arguments.get("unresolved", mem_type == "unresolved"))
        result = await memory_service.create_memory(
            content, tags=tag_list, layer=layer,
            memory_type=mem_type, event_date=event_date,
            unresolved=unresolved,
        )
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

    elif name == "read_jinger_diary":
        limit = arguments.get("limit", 5)
        diaries = await diary_service.list_diaries(author="jinger", limit=limit)
        if not diaries:
            return "静儿还没有写过日记。"
        parts = []
        for d in diaries:
            if d.get("locked"):
                parts.append(f"🔒【{d['title']}】(ID: {d['id']}) ({d['created_at'][:10]})\n（这篇上锁了，需要猜对密码才能看。你可以用 try_unlock_diary 试试，也可以在动态里留言问静儿。）")
            else:
                parts.append(f"【{d['title']}】(ID: {d['id']}) ({d['created_at'][:10]})\n{d['content']}")
        return "\n\n---\n\n".join(parts)

    elif name == "try_unlock_diary":
        diary_id = arguments.get("diary_id", "")
        pin = arguments.get("pin", "")
        if not diary_id or not pin:
            return "日记 ID 和密码都不能为空。"
        attempts = _unlock_attempts.get(diary_id, 0)
        if attempts >= MAX_UNLOCK_ATTEMPTS:
            return "你已经猜了太多次了，去动态里留言问静儿吧。"
        diary = await diary_interaction_service.get_diary(diary_id)
        if not diary:
            return "没有找到这篇日记。"
        if not diary.get("locked"):
            return "这篇日记没有上锁，直接用 read_jinger_diary 就能看。"
        if diary.get("pin") and pin == diary["pin"]:
            _unlock_attempts.pop(diary_id, None)
            return f"密码正确！解锁成功 🎉\n\n【{diary['title']}】\n{diary['content']}"
        _unlock_attempts[diary_id] = attempts + 1
        remaining = MAX_UNLOCK_ATTEMPTS - attempts - 1
        if remaining > 0:
            return f"密码不对。还能再试 {remaining} 次，猜不到就去动态里留言问静儿吧。"
        return "密码不对，已经没有机会了。去动态里留言问静儿吧。"

    elif name == "write_diary":
        title = arguments.get("title", "")
        content = arguments.get("content", "")
        locked = bool(arguments.get("locked", False))
        if not title or not content:
            return "标题和内容都不能为空。"
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
        note = await note_service.create_note(content)
        return json.dumps({
            "type": "note_created",
            "note": note,
            "message": "纸条已经悄悄放好了，静儿现在就能看到。",
        }, ensure_ascii=False)

    elif name == "get_current_time":
        now = datetime.now(timezone(timedelta(hours=8)))
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return f"现在是 {now.strftime('%Y年%m月%d日')} {weekdays[now.weekday()]} {now.strftime('%H:%M')}"

    elif name == "web_search":
        query = arguments.get("query", "")
        if not query:
            return "搜索关键词不能为空。"
        from app.services.web_service import web_search_ddg
        results = await web_search_ddg(query)
        if not results:
            return "没有搜到相关结果。"
        lines = []
        for r in results:
            lines.append(f"- [{r['title']}]({r['url']})\n  {r['snippet']}")
        return "\n".join(lines)

    elif name == "browse_url":
        url = arguments.get("url", "")
        if not url:
            return "网址不能为空。"
        from app.services.web_service import browse_url as _browse_url
        result = await _browse_url(url)
        if not result["ok"]:
            return f"打开网页失败：{result.get('error', '未知错误')}"
        data = result["data"]
        title = data.get("title") or data.get("h1") or ""
        body = data.get("body", "")[:3000]
        return f"【{title}】\n\n{body}" if title else body

    elif name == "browse_xiaohongshu":
        url = arguments.get("url", "")
        if not url:
            return "链接不能为空。"
        from app.services.web_service import browse_xiaohongshu as _browse_xhs
        result = await _browse_xhs(url)
        if not result["ok"]:
            return f"打开小红书失败：{result.get('error', '未知错误')}"
        data = result["data"]
        parts = []
        if data.get("author"):
            parts.append(f"作者：{data['author']}")
        if data.get("title"):
            parts.append(f"标题：{data['title']}")
        if data.get("content"):
            parts.append(f"\n{data['content']}")
        if data.get("likes"):
            parts.append(f"\n点赞：{data['likes']}")
        if data.get("comments"):
            parts.append("\n评论区：")
            for c in data["comments"][:20]:
                parts.append(f"  {c.get('user', '匿名')}：{c.get('text', '')}")
        return "\n".join(parts)

    elif name == "browse_twitter":
        url = arguments.get("url", "")
        if not url:
            return "链接不能为空。"
        from app.services.web_service import browse_twitter as _browse_tw
        result = await _browse_tw(url)
        if not result["ok"]:
            return f"打开推特失败：{result.get('error', '未知错误')}"
        data = result["data"]
        parts = []
        mt = data.get("mainTweet", {})
        if mt.get("author"):
            parts.append(f"{mt['author']}")
        if mt.get("text"):
            parts.append(mt["text"])
        if mt.get("time"):
            parts.append(f"({mt['time']})")
        if data.get("replies"):
            parts.append("\n回复：")
            for r in data["replies"][:15]:
                parts.append(f"  {r.get('author', '')}：{r.get('text', '')}")
        return "\n".join(parts)

    elif name == "search_xiaohongshu":
        query = arguments.get("query", "")
        if not query:
            return "搜索关键词不能为空。"
        from app.services.web_service import search_on_page
        result = await search_on_page("xiaohongshu", query)
        if not result["ok"]:
            return f"搜索小红书失败：{result.get('error', '未知错误')}"
        items = result.get("results", [])
        if not items:
            return "没有搜到相关笔记。"
        lines = []
        for item in items:
            title = item.get("title", "无标题")
            author = item.get("author", "")
            url = item.get("url", "")
            line = f"- {title}"
            if author:
                line += f"（{author}）"
            if url:
                line += f"\n  {url}"
            lines.append(line)
        return "\n".join(lines)

    elif name == "search_twitter":
        query = arguments.get("query", "")
        if not query:
            return "搜索关键词不能为空。"
        from app.services.web_service import search_on_page
        result = await search_on_page("twitter", query)
        if not result["ok"]:
            return f"搜索推特失败：{result.get('error', '未知错误')}"
        items = result.get("results", [])
        if not items:
            return "没有搜到相关推文。"
        lines = []
        for item in items:
            author = item.get("author", "")
            text = item.get("text", "")
            url = item.get("url", "")
            lines.append(f"- {author}：{text}" + (f"\n  {url}" if url else ""))
        return "\n".join(lines)

    elif name == "save_browsed":
        source = arguments.get("source", "web")
        title = arguments.get("title", "")
        url = arguments.get("url", "")
        summary = arguments.get("summary", "")
        tags_str = arguments.get("tags", "")
        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
        if not title or not summary:
            return "标题和总结不能为空。"
        from app.services.web_service import save_browsed_content
        content_id = await save_browsed_content(source, title, url, summary, tag_list)
        return f"已保存：【{title}】，之后可以分享给静儿。"

    elif name == "set_breath_state":
        text = arguments.get("text", "").strip()
        if not text:
            return "状态文字不能为空。"
        from app.database import get_db
        import uuid
        now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")
        async with get_db() as db:
            await db.execute(
                "INSERT INTO breath_states (id, content, created_at) VALUES (?, ?, ?)",
                (f"breath_{uuid.uuid4().hex[:12]}", text, now),
            )
            await db.commit()
        return f"状态已更新为「{text}」"

    return f"未知工具：{name}"
