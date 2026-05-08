import uuid
import json
from datetime import datetime
from app.database import get_db
from app.llm import call_llm, ModelConfig
from app.config import DAILY_API_BASE, DAILY_API_KEY, DAILY_MODEL_ID
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ──────────────────────────────────────
#  记忆提取（从聊天中生成候选）
# ──────────────────────────────────────

async def extract_candidates(conversation_id: str, messages: list[dict]) -> list[dict]:
    """分析最近的聊天消息，提取记忆候选。"""
    tagging_prompt = _load_prompt("tagging.md")
    if not tagging_prompt:
        return []

    chat_text = "\n".join(
        f"{'静儿' if m['role'] == 'user' else 'Connie'}: {m['content']}"
        for m in messages
    )

    llm_messages = [
        {"role": "system", "content": tagging_prompt},
        {"role": "user", "content": chat_text},
    ]

    config = ModelConfig(
        api_base=DAILY_API_BASE,
        api_key=DAILY_API_KEY,
        model_id=DAILY_MODEL_ID,
    )

    raw = await call_llm(config, llm_messages, stream=False, temperature=0.3, max_tokens=2000)

    candidates = _parse_candidates(raw)
    if not candidates:
        return []

    saved = []
    async with get_db() as db:
        for c in candidates:
            cid = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            await db.execute(
                """INSERT INTO memory_candidates
                   (id, conversation_id, content, tags_json, status, created_at)
                   VALUES (?, ?, ?, ?, 'pending', ?)""",
                (cid, conversation_id, c["content"], json.dumps(c.get("tags", []), ensure_ascii=False), now),
            )
            saved.append({"id": cid, "content": c["content"], "tags": c.get("tags", []),
                          "memory_type": c.get("memory_type", "fact"), "confidence": c.get("confidence", 0.5)})
        await db.commit()

    return saved


def _parse_candidates(raw: str) -> list[dict]:
    """解析 LLM 返回的 JSON 数组，跳过格式不对的条目。"""
    raw = raw.strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        items = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [item for item in items if isinstance(item, dict) and item.get("content")]


def _bigrams(text: str) -> set[str]:
    """把文本拆成双字词组的集合。比如 '静儿喜欢咖啡' → {'静儿', '儿喜', '喜欢', '欢咖', '咖啡'}"""
    text = text.strip()
    return {text[i:i+2] for i in range(len(text) - 1)}


# ──────────────────────────────────────
#  候选确认 / 拒绝
# ──────────────────────────────────────

async def accept_candidate(candidate_id: str, content: str | None = None,
                           memory_type: str | None = None, tags: list[str] | None = None) -> dict:
    """确认候选，写入正式记忆，返回关联的 top-3 旧记忆。"""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM memory_candidates WHERE id = ? AND status = 'pending'", (candidate_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("候选不存在或已处理")

        final_content = content or row["content"]
        final_tags = tags if tags is not None else json.loads(row["tags_json"] or "[]")
        final_type = memory_type or "fact"

        now = datetime.utcnow().isoformat()
        mem_id = str(uuid.uuid4())

        await db.execute(
            """INSERT INTO memories
               (id, content, tags_json, source_candidate_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mem_id, final_content, json.dumps(final_tags, ensure_ascii=False), candidate_id, now, now),
        )

        await db.execute(
            "UPDATE memory_candidates SET status = 'accepted' WHERE id = ?", (candidate_id,)
        )
        await db.commit()

    associated = await find_associated(final_content, final_tags, exclude_id=mem_id)

    return {
        "memory": {"id": mem_id, "content": final_content, "memory_type": final_type, "tags": final_tags},
        "associated": associated,
    }


async def reject_candidate(candidate_id: str):
    """拒绝候选。"""
    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM memory_candidates WHERE id = ? AND status = 'pending'", (candidate_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("候选不存在或已处理")

        await db.execute(
            "UPDATE memory_candidates SET status = 'rejected' WHERE id = ?", (candidate_id,)
        )
        await db.commit()


# ──────────────────────────────────────
#  记忆关联（写入时自动找 top-3）
# ──────────────────────────────────────

async def find_associated(content: str, tags: list[str], limit: int = 3,
                          exclude_id: str | None = None) -> list[dict]:
    """关键词 + 标签匹配，找 top-N 相关旧记忆。Phase 1 不用向量，纯文本匹配。"""
    async with get_db() as db:
        async with db.execute("SELECT * FROM memories ORDER BY created_at DESC") as cur:
            all_memories = await cur.fetchall()

    if not all_memories:
        return []

    content_grams = _bigrams(content)

    scored = []
    for mem in all_memories:
        if exclude_id and mem["id"] == exclude_id:
            continue
        mem_content = mem["content"]
        mem_tags = json.loads(mem["tags_json"] or "[]")

        tag_overlap = len(set(tags) & set(mem_tags))
        mem_grams = _bigrams(mem_content)
        gram_overlap = len(content_grams & mem_grams)
        content_score = min(gram_overlap / max(len(content_grams), 1), 1.0)

        score = tag_overlap * 0.4 + content_score * 0.6
        if score > 0.05:
            scored.append({"memory": mem, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)

    top = scored[:limit]
    if top:
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            for item in top:
                await db.execute(
                    "UPDATE memories SET updated_at = ? WHERE id = ?",
                    (now, item["memory"]["id"]),
                )
            await db.commit()

    return [
        {
            "id": item["memory"]["id"],
            "content": item["memory"]["content"],
            "tags": json.loads(item["memory"]["tags_json"] or "[]"),
            "relevance_score": round(item["score"], 2),
        }
        for item in top
    ]


# ──────────────────────────────────────
#  记忆召回（聊天前注入上下文）
# ──────────────────────────────────────

async def recall(query: str, limit: int = 5) -> list[dict]:
    """根据关键词召回相关记忆，用于注入聊天上下文。"""
    async with get_db() as db:
        async with db.execute("SELECT * FROM memories ORDER BY created_at DESC") as cur:
            all_memories = await cur.fetchall()

    if not all_memories:
        return []

    query_grams = _bigrams(query)

    scored = []
    for mem in all_memories:
        mem_content = mem["content"]
        mem_tags = json.loads(mem["tags_json"] or "[]")

        mem_grams = _bigrams(mem_content)
        gram_overlap = len(query_grams & mem_grams)
        content_score = min(gram_overlap / max(len(query_grams), 1), 1.0)

        tag_score = sum(1 for tag in mem_tags if tag in query) * 0.3

        keyword_score = 0
        query_lower = query.lower()
        for tag in mem_tags:
            if tag in query_lower:
                keyword_score += 0.4
        words = [w for w in mem_content.split() if len(w) >= 2]
        for w in words:
            if w in query_lower:
                keyword_score += 0.2

        score = content_score + tag_score + min(keyword_score, 1.0)
        if score > 0.05:
            scored.append({"memory": mem, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)

    results = scored[:limit]

    if len(results) < limit:
        already_ids = {item["memory"]["id"] for item in results}
        fallback_count = limit - len(results)
        for mem in all_memories[:fallback_count * 2]:
            if mem["id"] not in already_ids:
                results.append({"memory": mem, "score": 0.01})
                already_ids.add(mem["id"])
                if len(results) >= limit:
                    break

    return [
        {
            "id": item["memory"]["id"],
            "content": item["memory"]["content"],
            "tags": json.loads(item["memory"]["tags_json"] or "[]"),
            "relevance_score": round(item["score"], 2),
        }
        for item in results
    ]


# ──────────────────────────────────────
#  CRUD 辅助
# ──────────────────────────────────────

async def list_candidates(status: str = "pending", limit: int = 20, offset: int = 0) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM memory_candidates WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ) as cur:
            rows = await cur.fetchall()

    return [
        {
            "id": r["id"],
            "content": r["content"],
            "tags": json.loads(r["tags_json"] or "[]"),
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def list_memories(limit: int = 50, offset: int = 0, search: str | None = None) -> list[dict]:
    async with get_db() as db:
        if search:
            async with db.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (f"%{search}%", limit, offset),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ) as cur:
                rows = await cur.fetchall()

    return [
        {
            "id": r["id"],
            "content": r["content"],
            "tags": json.loads(r["tags_json"] or "[]"),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def get_memory(memory_id: str) -> dict | None:
    async with get_db() as db:
        async with db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "content": row["content"],
        "tags": json.loads(row["tags_json"] or "[]"),
        "created_at": row["created_at"],
    }


async def update_memory(memory_id: str, content: str | None = None, tags: list[str] | None = None) -> dict:
    async with get_db() as db:
        async with db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("记忆不存在")

        now = datetime.utcnow().isoformat()
        new_content = content if content is not None else row["content"]
        new_tags = json.dumps(tags, ensure_ascii=False) if tags is not None else row["tags_json"]

        await db.execute(
            "UPDATE memories SET content = ?, tags_json = ?, updated_at = ? WHERE id = ?",
            (new_content, new_tags, now, memory_id),
        )
        await db.commit()

    return {"id": memory_id, "content": new_content, "tags": json.loads(new_tags or "[]")}


async def delete_memory(memory_id: str):
    async with get_db() as db:
        async with db.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("记忆不存在")

        await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        await db.commit()
