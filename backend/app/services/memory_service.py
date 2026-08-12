import uuid
import json
import math
from datetime import datetime
from app.database import get_db
from app.llm import call_llm, get_embedding, get_embeddings_batch
from app.config import EMBEDDING_API_BASE, EMBEDDING_API_KEY, EMBEDDING_MODEL_ID
from app.services import model_settings_service
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
LAYERS = ("core", "long", "short", "consciousness")
MEMORY_TYPES = ("fact", "event", "unresolved", "date", "consciousness")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _generate_embedding(text: str) -> list[float] | None:
    return await get_embedding(EMBEDDING_API_BASE, EMBEDDING_API_KEY, EMBEDDING_MODEL_ID, text)


def _pack_embedding(emb: list[float]) -> bytes:
    return json.dumps(emb).encode("utf-8")


def _unpack_embedding(blob: bytes | None) -> list[float] | None:
    if not blob:
        return None
    try:
        return json.loads(blob)
    except Exception:
        return None


def _decay_rate_for_layer(layer: str) -> float:
    if layer in ("core", "consciousness"):
        return 0.0
    if layer == "short":
        return 0.95
    return 0.995


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ──────────────────────────────────────
#  记忆提取（从聊天中生成候选）
# ──────────────────────────────────────

async def extract_candidates(conversation_id: str, messages: list[dict]) -> list[dict]:
    """分析最近的聊天消息，提取记忆候选。confidence >= 0.7 自动入库，其余留 pending。"""
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

    config, slot_settings = await model_settings_service.get_model_config_for_slot("backend")

    raw = await call_llm(
        config,
        llm_messages,
        stream=False,
        temperature=0.3,
        max_tokens=2000,
        extended_thinking=bool(slot_settings.get("extended_thinking")),
    )

    candidates = _parse_candidates(raw)
    if not candidates:
        return []

    saved = []
    for c in candidates:
        content = c["content"]
        tags = c.get("tags", [])
        confidence = c.get("confidence", 0.5)

        if await _is_duplicate(content):
            continue

        mem_type = c.get("memory_type", "fact")
        proposed_layer = c.get("layer", "long")
        event_date = c.get("event_date")
        valence = max(0.0, min(1.0, float(c.get("valence", 0.5))))
        arousal = max(0.0, min(1.0, float(c.get("arousal", 0.0))))
        unresolved = bool(c.get("unresolved", mem_type == "unresolved")) or mem_type == "unresolved"

        if confidence >= 0.7:
            result = await create_memory(
                content, tags=tags, layer=proposed_layer,
                memory_type=mem_type, event_date=event_date,
                valence=valence, arousal=arousal,
                unresolved=unresolved,
            )
            if result["memory"].get("duplicate"):
                continue
            saved.append({
                "id": result["memory"]["id"],
                "content": content,
                "tags": tags,
                "memory_type": mem_type,
                "layer": proposed_layer,
                "confidence": confidence,
                "status": "accepted",
            })
        else:
            cid = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            async with get_db() as db:
                await db.execute(
                    """INSERT INTO memory_candidates
                       (id, conversation_id, content, tags_json,
                        proposed_memory_type, proposed_layer, confidence, proposed_event_date,
                        proposed_valence, proposed_arousal, proposed_unresolved,
                        status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                    (cid, conversation_id, content, json.dumps(tags, ensure_ascii=False),
                     mem_type, proposed_layer, confidence, event_date,
                     valence, arousal, int(unresolved), now),
                )
                await db.commit()
            saved.append({
                "id": cid,
                "content": content,
                "tags": tags,
                "memory_type": mem_type,
                "layer": proposed_layer,
                "confidence": confidence,
                "status": "pending",
            })

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


async def _is_duplicate(content: str, threshold: float = 0.6) -> bool:
    """检查新内容是否与已有记忆高度重复。"""
    async with get_db() as db:
        async with db.execute("SELECT content FROM memories ORDER BY created_at DESC LIMIT 200") as cur:
            rows = await cur.fetchall()
    if not rows:
        return False
    new_grams = _bigrams(content)
    if not new_grams:
        return False
    for row in rows:
        existing_grams = _bigrams(row["content"])
        if not existing_grams:
            continue
        overlap = len(new_grams & existing_grams)
        similarity = overlap / min(len(new_grams), len(existing_grams))
        if similarity >= threshold:
            return True
    return False


# ──────────────────────────────────────
#  候选确认 / 拒绝
# ──────────────────────────────────────

async def accept_candidate(candidate_id: str, content: str | None = None,
                           memory_type: str | None = None, tags: list[str] | None = None,
                           layer: str | None = None, event_date: str | None = None) -> dict:
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
        final_type = memory_type or _safe_get(row, "proposed_memory_type") or "fact"
        final_layer = layer or _safe_get(row, "proposed_layer") or "long"
        final_event_date = event_date or _safe_get(row, "proposed_event_date")
        final_valence = max(0.0, min(1.0, float(_safe_get(row, "proposed_valence") or 0.5)))
        final_arousal = max(0.0, min(1.0, float(_safe_get(row, "proposed_arousal") or 0.0)))
        final_unresolved = bool(_safe_get(row, "proposed_unresolved")) or final_type == "unresolved"
        if final_layer not in LAYERS:
            final_layer = "long"
        if final_type not in MEMORY_TYPES:
            final_type = "fact"

        if await _is_duplicate(final_content):
            raise ValueError("与已有记忆重复")

        mem_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        decay_rate = _decay_rate_for_layer(final_layer)
        embedding = await _generate_embedding(final_content)
        embedding_blob = _pack_embedding(embedding) if embedding else None

        await db.execute(
            """INSERT INTO memories
               (id, content, tags_json, layer, memory_type, event_date,
                weight, decay_rate, valence, arousal, unresolved, pinned,
                embedding, source_candidate_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mem_id, final_content, json.dumps(final_tags, ensure_ascii=False),
                final_layer, final_type, final_event_date, decay_rate,
                final_valence, final_arousal, int(final_unresolved),
                1 if final_layer == "core" else 0, embedding_blob,
                candidate_id, now, now,
            ),
        )
        await db.execute(
            "UPDATE memory_candidates SET status = 'accepted' WHERE id = ?", (candidate_id,)
        )
        await db.commit()

    associated = await find_associated(
        final_content, final_tags, exclude_id=mem_id, content_embedding=embedding
    )
    if associated:
        async with get_db() as db:
            for item in associated:
                await db.execute(
                    """INSERT INTO memory_links
                       (id, source_id, target_id, link_type, weight, created_at)
                       VALUES (?, ?, ?, 'relates_to', ?, ?)""",
                    (
                        str(uuid.uuid4()), mem_id, item["id"],
                        item.get("relevance_score", 0.5), datetime.utcnow().isoformat(),
                    ),
                )
            await db.commit()

    return {
        "memory": {
            "id": mem_id, "content": final_content, "memory_type": final_type,
            "tags": final_tags, "layer": final_layer, "event_date": final_event_date,
            "weight": 1.0,
        },
        "associated": associated,
    }


def _safe_get(row, key):
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


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
                          exclude_id: str | None = None,
                          content_embedding: list[float] | None = None) -> list[dict]:
    """找 top-N 相关旧记忆。有 embedding 用语义匹配，否则退回 bigram。"""
    async with get_db() as db:
        async with db.execute("SELECT * FROM memories ORDER BY created_at DESC") as cur:
            all_memories = await cur.fetchall()

    if not all_memories:
        return []

    query_emb = content_embedding or await _generate_embedding(content)
    use_embedding = query_emb is not None

    scored = []
    for mem in all_memories:
        if exclude_id and mem["id"] == exclude_id:
            continue
        mem_content = mem["content"]
        mem_tags = json.loads(mem["tags_json"] or "[]")

        if use_embedding:
            mem_emb = _unpack_embedding(mem["embedding"] if "embedding" in mem.keys() else None)
            if mem_emb:
                sim = _cosine_similarity(query_emb, mem_emb)
                tag_overlap = len(set(tags) & set(mem_tags))
                score = max(0, sim) * 0.7 + min(tag_overlap * 0.15, 0.3)
            else:
                tag_overlap = len(set(tags) & set(mem_tags))
                content_grams = _bigrams(content)
                mem_grams = _bigrams(mem_content)
                gram_overlap = len(content_grams & mem_grams)
                content_score = min(gram_overlap / max(len(content_grams), 1), 1.0)
                score = tag_overlap * 0.4 + content_score * 0.6
        else:
            tag_overlap = len(set(tags) & set(mem_tags))
            content_grams = _bigrams(content)
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
                    """UPDATE memories
                       SET last_triggered_at = ?, trigger_count = trigger_count + 1, updated_at = ?
                       WHERE id = ?""",
                    (now, now, item["memory"]["id"]),
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

async def get_core_memories() -> list[dict]:
    """获取所有核心记忆（core 层 或 pinned），每次聊天都必须带上。"""
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM memories WHERE layer = 'core' OR pinned = 1 ORDER BY created_at ASC"
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            "id": r["id"],
            "content": r["content"],
            "tags": json.loads(r["tags_json"] or "[]"),
            "relevance_score": 1.0,
        }
        for r in rows
    ]


async def recall(query: str, limit: int = 5) -> list[dict]:
    """双通道检索：关键词精确匹配 + 语义相似度，合并去重排序。"""
    async with get_db() as db:
        async with db.execute("SELECT * FROM memories ORDER BY created_at DESC") as cur:
            all_memories = await cur.fetchall()

    if not all_memories:
        return []

    core_ids = {m["id"] for m in all_memories if m["layer"] == "core" or m["pinned"]}
    non_core = [m for m in all_memories if m["id"] not in core_ids]

    # ── 通道 A：关键词搜索（精确命中名字、日期、短语） ──
    keyword_scores = {}
    for mem in non_core:
        mid = mem["id"]
        mem_content = mem["content"]
        mem_tags = json.loads(mem["tags_json"] or "[]")
        score = _keyword_search_score(query, mem_content, mem_tags)
        if score > 0:
            keyword_scores[mid] = score

    # ── 通道 B：语义搜索（embedding 余弦相似度） ──
    semantic_scores = {}
    query_emb = await _generate_embedding(query)
    if query_emb:
        for mem in non_core:
            mid = mem["id"]
            mem_emb = _unpack_embedding(mem["embedding"] if "embedding" in mem.keys() else None)
            if mem_emb:
                sim = _cosine_similarity(query_emb, mem_emb)
                if sim > 0.2:
                    semantic_scores[mid] = sim

    # ── 合并两个通道：同一条记忆取最高分 ──
    all_ids = set(keyword_scores.keys()) | set(semantic_scores.keys())
    mem_lookup = {m["id"]: m for m in non_core}

    scored = []
    for mid in all_ids:
        mem = mem_lookup[mid]
        kw_score = keyword_scores.get(mid, 0)
        sem_score = semantic_scores.get(mid, 0)
        raw_score = max(kw_score, sem_score)

        layer_weight = {"core": 1.0, "long": 0.9, "short": 0.7, "consciousness": 0.6}.get(mem["layer"], 0.8)
        mem_weight = mem["weight"] or 1.0
        arousal_val = mem["arousal"] if "arousal" in mem.keys() and mem["arousal"] else 0.0
        final_score = raw_score * layer_weight * (1 + arousal_val * 0.3) * mem_weight
        is_resolved_task = (mem["memory_type"] == "unresolved" and not mem["unresolved"])
        if is_resolved_task:
            final_score *= 0.3

        if final_score > 0.05:
            scored.append({"memory": mem, "score": final_score})

    scored.sort(key=lambda x: x["score"], reverse=True)

    results = scored[:limit]

    if len(results) < limit:
        import random
        already_ids = {item["memory"]["id"] for item in results} | core_ids
        remaining = [m for m in non_core if m["id"] not in already_ids]
        if remaining and random.random() < 0.4:
            drift = random.choice(remaining)
            results.append({"memory": drift, "score": 0.02})
            already_ids.add(drift["id"])
        fallback_count = limit - len(results)
        for mem in remaining[:fallback_count * 2]:
            if mem["id"] not in already_ids:
                results.append({"memory": mem, "score": 0.01})
                already_ids.add(mem["id"])
                if len(results) >= limit:
                    break

    if results:
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            for item in results:
                if item["score"] > 0.05:
                    await db.execute(
                        """UPDATE memories
                           SET last_triggered_at = ?,
                               trigger_count = trigger_count + 1,
                               weight = MIN(1.0, weight + 0.1),
                               updated_at = ?
                           WHERE id = ?""",
                        (now, now, item["memory"]["id"]),
                    )
                    mem = item["memory"]
                    new_trigger = (mem["trigger_count"] or 0) + 1
                    if mem["layer"] in ("short", "consciousness") and new_trigger >= 3:
                        await db.execute(
                            """UPDATE memories SET layer = 'long', decay_rate = ?
                               WHERE id = ? AND layer IN ('short', 'consciousness')""",
                            (_decay_rate_for_layer("long"), mem["id"]),
                        )
                        _digest_logger.info("auto-promote: %s → long (triggered %d times)", mem["id"][:8], new_trigger)
            await db.commit()

    return [
        {
            "id": item["memory"]["id"],
            "content": item["memory"]["content"],
            "tags": json.loads(item["memory"]["tags_json"] or "[]"),
            "relevance_score": round(item["score"], 2),
        }
        for item in results
    ]


def _keyword_search_score(query: str, mem_content: str, mem_tags: list[str]) -> float:
    """通道 A：关键词精确匹配。适合名字、日期、具体短语。"""
    score = 0.0
    query_lower = query.lower()
    content_lower = mem_content.lower()

    query_chars = set(query_lower)
    keywords = []
    for tag in mem_tags:
        if tag.lower() in query_lower:
            score += 0.4
    for word in query.split():
        if len(word) >= 2 and word in content_lower:
            score += 0.3
    if len(query) >= 3 and query_lower in content_lower:
        score += 0.8

    return min(score, 2.0)


def _bigram_score(query: str, mem_content: str, mem_tags: list[str]) -> float:
    query_grams = _bigrams(query)
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

    return content_score + tag_score + min(keyword_score, 1.0)


# ──────────────────────────────────────
#  直接写入记忆（MCP / 手动）
# ──────────────────────────────────────

async def create_memory(content: str, tags: list[str] | None = None,
                        layer: str = "long", memory_type: str = "fact",
                        event_date: str | None = None, event_time: str | None = None,
                        valence: float = 0.0, arousal: float = 0.0,
                        unresolved: bool = False) -> dict:
    """直接写入正式记忆（跳过候选流程），写入前去重，返回记忆 + 关联旧记忆。"""
    tags = tags or []
    content = content.strip()
    if not content:
        raise ValueError("记忆内容不能为空")
    if layer not in LAYERS:
        layer = "long"
    if memory_type not in MEMORY_TYPES:
        memory_type = "fact"
    if memory_type == "unresolved":
        unresolved = True
    elif unresolved:
        memory_type = "unresolved"

    if await _is_duplicate(content):
        return {"memory": {"id": None, "content": content, "tags": tags, "duplicate": True}, "associated": []}

    mem_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    decay_rate = _decay_rate_for_layer(layer)

    emb = await _generate_embedding(content)
    emb_blob = _pack_embedding(emb) if emb else None

    async with get_db() as db:
        await db.execute(
            """INSERT INTO memories
               (id, content, tags_json, layer, memory_type, event_date, event_time,
                weight, decay_rate, valence, arousal, unresolved, pinned,
                embedding, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mem_id, content, json.dumps(tags, ensure_ascii=False),
             layer, memory_type, event_date, event_time,
             decay_rate, valence, arousal, int(unresolved),
             1 if layer == "core" else 0, emb_blob, now, now),
        )
        await db.commit()

    associated = await find_associated(content, tags, limit=3, exclude_id=mem_id, content_embedding=emb)

    if associated:
        async with get_db() as db:
            for a in associated:
                link_id = str(uuid.uuid4())
                now2 = datetime.utcnow().isoformat()
                await db.execute(
                    """INSERT OR IGNORE INTO memory_links
                       (id, source_id, target_id, link_type, weight, created_at)
                       VALUES (?, ?, ?, 'relates_to', ?, ?)""",
                    (link_id, mem_id, a["id"], a.get("relevance_score", 0.5), now2),
                )
            await db.commit()

    return {
        "memory": {
            "id": mem_id, "content": content, "tags": tags,
            "layer": layer, "memory_type": memory_type,
            "event_date": event_date, "weight": 1.0,
        },
        "associated": associated,
    }


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
            "memory_type": _safe_get(r, "proposed_memory_type") or "fact",
            "layer": _safe_get(r, "proposed_layer") or "long",
            "confidence": _safe_get(r, "confidence") if _safe_get(r, "confidence") is not None else 0.5,
            "event_date": _safe_get(r, "proposed_event_date"),
            "valence": _safe_get(r, "proposed_valence") if _safe_get(r, "proposed_valence") is not None else 0.5,
            "arousal": _safe_get(r, "proposed_arousal") if _safe_get(r, "proposed_arousal") is not None else 0.0,
            "unresolved": bool(_safe_get(r, "proposed_unresolved")),
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def list_memories(limit: int = 50, offset: int = 0, search: str | None = None,
                        layer: str | None = None, memory_type: str | None = None,
                        date_from: str | None = None, date_to: str | None = None,
                        sort_by: str = "created_at") -> dict:
    conditions = []
    params = []

    if layer:
        conditions.append("layer = ?")
        params.append(layer)
    if memory_type:
        conditions.append("memory_type = ?")
        params.append(memory_type)
    if search:
        conditions.append("content LIKE ?")
        params.append(f"%{search}%")
    if date_from:
        conditions.append("(event_date >= ? OR (event_date IS NULL AND created_at >= ?))")
        params.extend([date_from, date_from])
    if date_to:
        conditions.append("(event_date <= ? OR (event_date IS NULL AND created_at <= ?))")
        params.extend([date_to, date_to + "T23:59:59"])

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    order = "weight DESC, created_at DESC" if sort_by == "weight" else "created_at DESC"

    async with get_db() as db:
        async with db.execute(
            f"SELECT * FROM memories{where} ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ) as cur:
            rows = await cur.fetchall()

        async with db.execute(
            f"SELECT COUNT(*) as cnt FROM memories{where}",
            params,
        ) as cur:
            total_row = await cur.fetchone()
            total = total_row["cnt"] if total_row else 0

    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
    }


def _row_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "content": r["content"],
        "tags": json.loads(r["tags_json"] or "[]"),
        "layer": r["layer"] if "layer" in r.keys() else "long",
        "memory_type": r["memory_type"] if "memory_type" in r.keys() else "fact",
        "event_date": r["event_date"] if "event_date" in r.keys() else None,
        "event_time": r["event_time"] if "event_time" in r.keys() else None,
        "weight": r["weight"] if "weight" in r.keys() else 1.0,
        "valence": r["valence"] if "valence" in r.keys() else 0.0,
        "arousal": r["arousal"] if "arousal" in r.keys() else 0.0,
        "pinned": bool(r["pinned"]) if "pinned" in r.keys() else False,
        "unresolved": bool(r["unresolved"]) if "unresolved" in r.keys() else False,
        "trigger_count": r["trigger_count"] if "trigger_count" in r.keys() else 0,
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


async def get_memory(memory_id: str) -> dict | None:
    async with get_db() as db:
        async with db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return _row_to_dict(row)


async def update_memory(memory_id: str, content: str | None = None, tags: list[str] | None = None,
                        layer: str | None = None, memory_type: str | None = None,
                        event_date: str | None = ..., event_time: str | None = ...,
                        valence: float | None = None, arousal: float | None = None,
                        unresolved: bool | None = None, pinned: bool | None = None) -> dict:
    new_embedding_blob = ...
    if content is not None:
        content = content.strip()
        if not content:
            raise ValueError("记忆内容不能为空")
        new_embedding = await _generate_embedding(content)
        new_embedding_blob = _pack_embedding(new_embedding) if new_embedding else None

    async with get_db() as db:
        async with db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("记忆不存在")

        now = datetime.utcnow().isoformat()
        updates = {"updated_at": now}

        if content is not None:
            updates["content"] = content
            # Never retain a vector for text it no longer represents. If the
            # provider is unavailable, backfill_embeddings() can restore it later.
            updates["embedding"] = new_embedding_blob
        if tags is not None:
            updates["tags_json"] = json.dumps(tags, ensure_ascii=False)
        if layer is not None and layer in LAYERS:
            updates["layer"] = layer
            updates["pinned"] = 1 if layer == "core" else 0
            updates["decay_rate"] = _decay_rate_for_layer(layer)
        if memory_type is not None and memory_type in MEMORY_TYPES:
            updates["memory_type"] = memory_type
            if unresolved is None:
                updates["unresolved"] = int(memory_type == "unresolved")
        if event_date is not ...:
            updates["event_date"] = event_date
        if event_time is not ...:
            updates["event_time"] = event_time
        if valence is not None:
            updates["valence"] = valence
        if arousal is not None:
            updates["arousal"] = arousal
        if unresolved is not None:
            updates["unresolved"] = int(unresolved)
            if unresolved:
                updates["memory_type"] = "unresolved"
        if pinned is not None and layer is None:
            if pinned:
                updates["pinned"] = 1
                updates["layer"] = "core"
                updates["decay_rate"] = _decay_rate_for_layer("core")
                updates["weight"] = 1.0
            else:
                current_layer = row["layer"] if "layer" in row.keys() else "long"
                target_layer = "long" if current_layer == "core" else current_layer
                updates["pinned"] = 0
                updates["layer"] = target_layer
                updates["decay_rate"] = _decay_rate_for_layer(target_layer)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values())
        values.append(memory_id)

        await db.execute(f"UPDATE memories SET {set_clause} WHERE id = ?", values)
        await db.commit()

        async with db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)) as cur:
            updated = await cur.fetchone()

    return _row_to_dict(updated)


async def resolve_memory(memory_id: str) -> dict:
    """Mark an active unresolved memory as completed without erasing its history."""
    async with get_db() as db:
        async with db.execute(
            "SELECT memory_type, unresolved FROM memories WHERE id = ?", (memory_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise ValueError("记忆不存在")
        if row["memory_type"] != "unresolved" and not row["unresolved"]:
            raise ValueError("这条记忆不是未完成事项")
        await db.execute(
            "UPDATE memories SET memory_type = 'unresolved', unresolved = 0, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), memory_id),
        )
        await db.commit()
    return await get_memory(memory_id)


async def move_layer(memory_id: str, target_layer: str) -> dict:
    if target_layer not in LAYERS:
        raise ValueError(f"无效层级: {target_layer}")
    return await update_memory(memory_id, layer=target_layer)


async def delete_memory(memory_id: str):
    async with get_db() as db:
        async with db.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("记忆不存在")

        await db.execute("DELETE FROM memory_links WHERE source_id = ? OR target_id = ?",
                         (memory_id, memory_id))
        await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        await db.commit()


async def get_layer_stats() -> dict:
    async with get_db() as db:
        async with db.execute(
            "SELECT layer, COUNT(*) as cnt FROM memories GROUP BY layer"
        ) as cur:
            rows = await cur.fetchall()
    stats = {"core": 0, "long": 0, "short": 0, "consciousness": 0, "total": 0}
    for r in rows:
        lyr = r["layer"]
        if lyr in stats:
            stats[lyr] = r["cnt"]
        stats["total"] += r["cnt"]
    return stats


async def get_heatmap(year: int, month: int) -> list[dict]:
    if month < 1 or month > 12:
        return []
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"

    async with get_db() as db:
        async with db.execute("""
            SELECT
                COALESCE(event_date, substr(created_at, 1, 10)) as day,
                COUNT(*) as cnt
            FROM memories
            WHERE COALESCE(event_date, substr(created_at, 1, 10)) >= ?
              AND COALESCE(event_date, substr(created_at, 1, 10)) < ?
            GROUP BY day
            ORDER BY day
        """, (start, end)) as cur:
            rows = await cur.fetchall()

    return [{"date": r["day"], "count": r["cnt"]} for r in rows]


# ──────────────────────────────────────
#  记忆整合（定时去重）
# ──────────────────────────────────────

import logging
_digest_logger = logging.getLogger(__name__)


async def run_digest():
    """用 LLM 识别并清理重复记忆。按层分批处理。"""
    digest_prompt = _load_prompt("digest.md")
    if not digest_prompt:
        _digest_logger.warning("digest: digest.md 不存在，跳过")
        return

    config, _ = await model_settings_service.get_model_config_for_slot("backend")
    total_deleted = 0

    for layer in ("core", "long", "short", "consciousness"):
        async with get_db() as db:
            async with db.execute(
                "SELECT id, content, layer, memory_type FROM memories WHERE layer = ? ORDER BY created_at",
                (layer,),
            ) as cur:
                rows = await cur.fetchall()

        if len(rows) < 2:
            continue

        chunks = []
        chunk_size = 15
        for i in range(0, len(rows), chunk_size):
            chunks.append(rows[i:i + chunk_size])

        for chunk in chunks:
            lines = []
            for r in chunk:
                lines.append(f"[{r['id']}] {r['content']} ({r['layer']}/{r['memory_type']})")
            input_text = "\n".join(lines)

            try:
                raw = await call_llm(
                    config,
                    [
                        {"role": "system", "content": digest_prompt},
                        {"role": "user", "content": input_text},
                    ],
                    stream=False,
                    temperature=0.2,
                    max_tokens=2000,
                )

                _digest_logger.info("digest: %s 层 LLM 返回 %d 字符", layer, len(raw))
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                brace_start = cleaned.find("{")
                brace_end = cleaned.rfind("}")
                if brace_start == -1 or brace_end == -1:
                    _digest_logger.warning("digest: %s 层 LLM 返回无 JSON，跳过", layer)
                    continue
                cleaned = cleaned[brace_start:brace_end + 1]
                result = json.loads(cleaned)

                ids_to_delete = set(result.get("delete", []))
                for merge in result.get("merge", []):
                    ids_to_delete.update(merge.get("delete_ids", []))

                if ids_to_delete:
                    async with get_db() as db:
                        for mid in ids_to_delete:
                            await db.execute("DELETE FROM memories WHERE id = ?", (mid,))
                            await db.execute("DELETE FROM memory_links WHERE source_id = ? OR target_id = ?", (mid, mid))
                        await db.commit()
                    total_deleted += len(ids_to_delete)
                    _digest_logger.info("digest: %s 层删除 %d 条重复记忆", layer, len(ids_to_delete))

            except Exception as e:
                _digest_logger.warning("digest: %s 层处理失败 — %s", layer, e)

    _digest_logger.info("digest: 完成，共删除 %d 条重复记忆", total_deleted)
    return total_deleted


# ──────────────────────────────────────
#  Embedding 回填
# ──────────────────────────────────────

async def backfill_embeddings(batch_size: int = 20) -> int:
    """给所有没有 embedding 的记忆生成向量。返回成功数量。"""
    if not all([EMBEDDING_API_BASE, EMBEDDING_API_KEY, EMBEDDING_MODEL_ID]):
        _digest_logger.warning("backfill: embedding 配置不完整，跳过")
        return 0

    async with get_db() as db:
        async with db.execute(
            "SELECT id, content FROM memories WHERE embedding IS NULL ORDER BY created_at"
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        _digest_logger.info("backfill: 所有记忆都已有 embedding")
        return 0

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        texts = [r["content"] for r in batch]
        embeddings = await get_embeddings_batch(
            EMBEDDING_API_BASE, EMBEDDING_API_KEY, EMBEDDING_MODEL_ID, texts
        )

        async with get_db() as db:
            for row, emb in zip(batch, embeddings):
                if emb:
                    await db.execute(
                        "UPDATE memories SET embedding = ? WHERE id = ?",
                        (_pack_embedding(emb), row["id"]),
                    )
                    total += 1
            await db.commit()

        _digest_logger.info("backfill: 已处理 %d/%d", min(i + batch_size, len(rows)), len(rows))

    _digest_logger.info("backfill: 完成，共生成 %d 条 embedding", total)
    return total


# ──────────────────────────────────────
#  情感标注回填
# ──────────────────────────────────────

EMOTION_PROMPT = """你是情感标注器。给每条记忆标注两个值：

valence（情感正负，0~1）：0=极度消极，0.5=中性，1=极度积极
arousal（情绪强度，0~1）：0=完全平静（日常事实），1=极度强烈（大哭/狂喜）

纯事实（职业、偏好、日期）→ valence=0.5, arousal=0.0
有情感的事件要认真评估。

输入格式：每行 [id] 内容
输出格式：严格只返回 JSON 对象，key 是 id，value 是 [valence, arousal]。

示例输出：
{"abc123": [0.7, 0.3], "def456": [0.3, 0.6]}"""


async def backfill_emotions(batch_size: int = 10) -> int:
    """用 LLM 给 valence=0 且 arousal=0 的记忆补标情感值。"""
    config, _ = await model_settings_service.get_model_config_for_slot("backend")

    async with get_db() as db:
        async with db.execute(
            """SELECT id, content FROM memories
               WHERE (valence = 0.0 OR valence IS NULL)
                 AND (arousal = 0.0 OR arousal IS NULL)
               ORDER BY created_at""",
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        _digest_logger.info("emotion-backfill: 所有记忆都已有情感标注")
        return 0

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        lines = [f"[{r['id']}] {r['content']}" for r in batch]
        input_text = "\n".join(lines)

        try:
            raw = await call_llm(
                config,
                [
                    {"role": "system", "content": EMOTION_PROMPT},
                    {"role": "user", "content": input_text},
                ],
                stream=False,
                temperature=0.2,
                max_tokens=1500,
            )

            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            brace_start = cleaned.find("{")
            brace_end = cleaned.rfind("}")
            if brace_start == -1 or brace_end == -1:
                _digest_logger.warning("emotion-backfill: LLM 返回无 JSON，跳过这批")
                continue
            result = json.loads(cleaned[brace_start:brace_end + 1])

            async with get_db() as db:
                for mid, vals in result.items():
                    if isinstance(vals, list) and len(vals) == 2:
                        v = max(0.0, min(1.0, float(vals[0])))
                        a = max(0.0, min(1.0, float(vals[1])))
                        await db.execute(
                            "UPDATE memories SET valence = ?, arousal = ?, updated_at = ? WHERE id = ?",
                            (v, a, datetime.utcnow().isoformat(), mid),
                        )
                        total += 1
                await db.commit()

            _digest_logger.info("emotion-backfill: 已处理 %d/%d", min(i + batch_size, len(rows)), len(rows))

        except Exception as e:
            _digest_logger.warning("emotion-backfill: 处理失败 — %s", e)

    _digest_logger.info("emotion-backfill: 完成，共标注 %d 条记忆", total)
    return total
