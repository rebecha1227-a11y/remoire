import uuid
import json
from datetime import datetime
from app.database import get_db
from app.llm import call_llm
from app.services import model_settings_service
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
LAYERS = ("core", "long", "short", "consciousness")


def _decay_rate_for_layer(layer: str) -> float:
    if layer == "core":
        return 0.0
    if layer in ("short", "consciousness"):
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

        if confidence >= 0.7:
            result = await create_memory(
                content, tags=tags, layer=proposed_layer,
                memory_type=mem_type, event_date=event_date,
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
                        status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                    (cid, conversation_id, content, json.dumps(tags, ensure_ascii=False),
                     mem_type, proposed_layer, confidence, event_date, now),
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
        if final_layer not in LAYERS:
            final_layer = "long"

        if await _is_duplicate(final_content):
            raise ValueError("与已有记忆重复")

        mem_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        decay_rate = _decay_rate_for_layer(final_layer)

        await db.execute(
            """INSERT INTO memories
               (id, content, tags_json, layer, memory_type, event_date,
                weight, decay_rate, pinned, source_candidate_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?)""",
            (
                mem_id, final_content, json.dumps(final_tags, ensure_ascii=False),
                final_layer, final_type, final_event_date, decay_rate,
                1 if final_layer == "core" else 0, candidate_id, now, now,
            ),
        )
        await db.execute(
            "UPDATE memory_candidates SET status = 'accepted' WHERE id = ?", (candidate_id,)
        )
        await db.commit()

    associated = await find_associated(final_content, final_tags, exclude_id=mem_id)
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

    if results:
        now = datetime.utcnow().isoformat()
        async with get_db() as db:
            for item in results:
                if item["score"] > 0.05:
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
        for item in results
    ]


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
    if layer not in LAYERS:
        layer = "long"

    if await _is_duplicate(content):
        return {"memory": {"id": None, "content": content, "tags": tags, "duplicate": True}, "associated": []}

    mem_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    decay_rate = _decay_rate_for_layer(layer)

    async with get_db() as db:
        await db.execute(
            """INSERT INTO memories
               (id, content, tags_json, layer, memory_type, event_date, event_time,
                weight, decay_rate, valence, arousal, unresolved, pinned,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, ?, ?, ?, ?)""",
            (mem_id, content, json.dumps(tags, ensure_ascii=False),
             layer, memory_type, event_date, event_time,
             decay_rate, valence, arousal, int(unresolved),
             1 if layer == "core" else 0, now, now),
        )
        await db.commit()

    associated = await find_associated(content, tags, limit=3, exclude_id=mem_id)

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
    async with get_db() as db:
        async with db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("记忆不存在")

        now = datetime.utcnow().isoformat()
        updates = {"updated_at": now}

        if content is not None:
            updates["content"] = content
        if tags is not None:
            updates["tags_json"] = json.dumps(tags, ensure_ascii=False)
        if layer is not None and layer in LAYERS:
            updates["layer"] = layer
            updates["pinned"] = 1 if layer == "core" else 0
            updates["decay_rate"] = _decay_rate_for_layer(layer)
        if memory_type is not None:
            updates["memory_type"] = memory_type
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
