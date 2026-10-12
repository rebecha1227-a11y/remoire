"""iMessage door into the existing chat, memory, and prompt path.

The Node bridge only moves text. This module decides who may speak, merges
bursts, and asks the same chat service the web uses.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx

from app.database import get_db
from app.services import imessage_interactions
from app.services.imessage_format import (
    FAILURE_PHRASE,
    INGRESS_NOTE,
    bubble_delay_ms,
    normalize_phone,
    sanitize_bubbles,
)
from app.services.model_settings_service import _decrypt_api_key, _encrypt_api_key

logger = logging.getLogger("remoire.imessage")

PHOTON_BASE = "https://spectrum.photon.codes"
_LOCK = asyncio.Lock()
_QUEUE = asyncio.Lock()
_STATE = {"items": [], "task": None, "auto_fire": True, "last_received": 0.0}


def reset_runtime_state():
    task = _STATE.get("task")
    if task and not task.done():
        task.cancel()
    _STATE["items"] = []
    _STATE["task"] = None
    _STATE["auto_fire"] = True
    _STATE["last_received"] = 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(value: str, limit: int = 300) -> str:
    text = (value or "").replace("\n", " ").strip()
    return text[:limit]


async def _ensure_account(db) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO imessage_accounts (id, updated_at) VALUES (1, ?)",
        (_now(),),
    )


async def get_account(*, include_secret: bool = False) -> dict:
    async with get_db() as db:
        await _ensure_account(db)
        await db.commit()
        async with db.execute("SELECT * FROM imessage_accounts WHERE id = 1") as cur:
            row = await cur.fetchone()
    data = dict(row)
    stored = data.get("project_secret") or ""
    data["secret_saved"] = bool(stored)
    if include_secret:
        data["project_secret"] = _decrypt_api_key(stored) if stored else ""
    else:
        data.pop("project_secret", None)
    data["enabled"] = bool(data.get("enabled"))
    data["failure_phrase_enabled"] = bool(data.get("failure_phrase_enabled"))
    return data


def public_account(account: dict) -> dict:
    hidden = {"project_secret", "chat_guid"}
    view = {key: value for key, value in account.items() if key not in hidden}
    view["secret_saved"] = bool(account.get("secret_saved") or account.get("project_secret"))
    view["enabled"] = bool(view.get("enabled"))
    view["failure_phrase_enabled"] = bool(view.get("failure_phrase_enabled"))
    return view


async def save_account(fields: dict) -> dict:
    current = await get_account(include_secret=True)
    enabled = int(fields["enabled"]) if "enabled" in fields else int(current["enabled"])
    project_id = fields.get("project_id", current.get("project_id") or "")
    owner_phone = normalize_phone(fields["owner_phone"]) if "owner_phone" in fields else current.get("owner_phone") or ""
    merge_wait = fields.get("merge_wait_seconds", current.get("merge_wait_seconds") or 4)
    typing_ms = fields.get("typing_ms_per_char", current.get("typing_ms_per_char") or 45)
    failure_on = fields.get("failure_phrase_enabled", current.get("failure_phrase_enabled"))
    secret = fields["project_secret"] if fields.get("project_secret") else (current.get("project_secret") or "")
    secret = _encrypt_api_key(secret) if secret else ""
    merge_wait = max(2, min(10, int(merge_wait)))
    typing_ms = max(20, min(200, int(typing_ms)))
    async with get_db() as db:
        await _ensure_account(db)
        await db.execute(
            """UPDATE imessage_accounts
               SET enabled = ?, project_id = ?, project_secret = ?, owner_phone = ?,
                   merge_wait_seconds = ?, typing_ms_per_char = ?,
                   failure_phrase_enabled = ?, updated_at = ?
               WHERE id = 1""",
            (
                enabled,
                project_id.strip(),
                secret,
                owner_phone,
                merge_wait,
                typing_ms,
                1 if failure_on else 0,
                _now(),
            ),
        )
        await db.commit()
    return public_account(await get_account())


async def set_status(status: str, detail: str = "", *, chat_guid: str = "", line_phone: str = "") -> None:
    allowed = {"unconfigured", "connecting", "connected", "line_changed", "failed"}
    if status not in allowed:
        status = "failed"
        detail = "状态无法识别"
    account = await get_account(include_secret=True)
    secret = account.get("project_secret") or ""
    safe_detail = _clip(detail)
    if secret and secret in safe_detail:
        safe_detail = "状态已更新"
    async with get_db() as db:
        await _ensure_account(db)
        await db.execute(
            """UPDATE imessage_accounts
               SET status = ?, status_detail = ?,
                   chat_guid = CASE WHEN ? != '' THEN ? ELSE chat_guid END,
                   line_phone = CASE WHEN ? != '' THEN ? ELSE line_phone END,
                   updated_at = ?
               WHERE id = 1""",
            (status, safe_detail, chat_guid, chat_guid, line_phone, normalize_phone(line_phone) if line_phone else "", _now()),
        )
        await db.commit()


async def mark_outbound() -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE imessage_accounts SET last_outbound_at = ?, updated_at = ?, status = CASE WHEN enabled = 1 AND status IN ('failed', 'connecting', 'connected') THEN 'connected' ELSE status END, status_detail = CASE WHEN enabled = 1 AND status IN ('failed', 'connecting', 'connected') THEN '' ELSE status_detail END WHERE id = 1",
            (_now(), _now()),
        )
        await db.commit()


async def enroll_line() -> dict:
    account = await get_account(include_secret=True)
    project_id = (account.get("project_id") or "").strip()
    secret = account.get("project_secret") or ""
    phone = normalize_phone(account.get("owner_phone") or "")
    if not project_id or not secret or not phone:
        raise ValueError("先填写项目编号、密钥和你的手机号")
    auth = _basic_auth(project_id, secret)
    async with httpx.AsyncClient(timeout=20) as client:
        listed = await client.get(
            f"{PHOTON_BASE}/projects/{project_id}/users/",
            headers={"Authorization": auth},
        )
        assigned = _assigned_from_list(listed, phone) if listed.status_code == 200 else ""
        if not assigned:
            created = await client.post(
                f"{PHOTON_BASE}/projects/{project_id}/users/",
                headers={"Authorization": auth, "Content-Type": "application/json"},
                json={"type": "shared", "phoneNumber": phone},
            )
            if created.status_code >= 400:
                logger.info("imessage_enroll_http status=%s", created.status_code)
                raise ValueError("开通线路没有成功，请核对项目编号和密钥")
            payload = created.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            assigned = (data or payload or {}).get("assignedPhoneNumber") or ""
    if not assigned:
        raise ValueError("Photon 没有返回线路号码")
    async with get_db() as db:
        await db.execute(
            "UPDATE imessage_accounts SET line_phone = ?, updated_at = ? WHERE id = 1",
            (assigned, _now()),
        )
        await db.commit()
    logger.info("imessage_enroll_ok")
    return public_account(await get_account())


def _basic_auth(project_id: str, secret: str) -> str:
    import base64
    token = base64.b64encode(f"{project_id}:{secret}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _assigned_from_list(response, phone: str) -> str:
    try:
        body = response.json()
    except Exception:
        return ""
    data = body.get("data") if isinstance(body, dict) else None
    users = []
    if isinstance(data, dict):
        users = data.get("users") or []
    elif isinstance(data, list):
        users = data
    for user in users:
        if user.get("phoneNumber") == phone and user.get("assignedPhoneNumber"):
            return user["assignedPhoneNumber"]
    return ""


async def _remember_inbox(external_id: str, accepted: int) -> bool:
    """Return True when this Photon id is new."""
    async with get_db() as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO imessage_inbox (external_id, accepted, created_at) VALUES (?, ?, ?)",
            (external_id, accepted, _now()),
        )
        await db.commit()
        return cur.rowcount == 1


async def accept_inbound(*, external_id: str, sender: str, text: str, sent_at: str = "", chat_guid: str = "", kind: str = "text", reply_to: str = "", quote_text: str = "", target_id: str = "", emoji: str = "", target_text: str = "", images: list[str] | None = None) -> dict:
    external_id = (external_id or "").strip()
    if not external_id:
        return {"ok": False, "reason": "missing_id"}
    sender_phone = normalize_phone(sender)
    account = await get_account()

    if not account.get("enabled"):
        logger.info("imessage_inbound_disabled")
        return {"ok": False, "reason": "disabled"}

    owner = normalize_phone(account.get("owner_phone") or "")
    if not owner or sender_phone != owner:
        logger.info("imessage_inbound_rejected")
        return {"ok": False, "reason": "rejected"}

    images = images or []
    from app.services.image_storage import decode_image, InvalidImageError, MAX_IMAGE_BYTES
    try:
        if len(images) > 4 or sum(len(decode_image(value)[0]) for value in images) > MAX_IMAGE_BYTES:
            raise InvalidImageError("图片总大小超过限制")
    except (InvalidImageError, TypeError):
        return {"ok": False, "reason": "invalid_image"}
    fresh = await _remember_inbox(external_id, 0)
    if not fresh:
        return {"ok": True, "duplicate": True}

    if kind == "reaction":
        if not chat_guid or not target_id or not emoji or len(emoji) > 32:
            return {"ok": False, "reason": "invalid_reaction"}
        await imessage_interactions.record_reaction(chat_guid, target_id, "user", emoji, target_text)
        return {"ok": True, "reaction_saved": True}

    # Non-text Photon events must not reset the debounce or supersede a reply.
    if not (text or "").strip() and not images:
        return {"ok": True, "ignored": "empty_text"}

    _note_lag(sent_at)
    async with get_db() as db:
        await db.execute(
            "UPDATE imessage_inbox SET accepted = 1 WHERE external_id = ?",
            (external_id,),
        )
        await db.execute(
            """UPDATE imessage_accounts
               SET status = CASE WHEN enabled = 1 AND status IN ('failed', 'connecting', 'connected') THEN 'connected' ELSE status END, status_detail = CASE WHEN enabled = 1 AND status IN ('failed', 'connecting', 'connected') THEN '' ELSE status_detail END, last_inbound_at = ?, chat_guid = CASE WHEN ? != '' THEN ? ELSE chat_guid END, updated_at = ?
               WHERE id = 1""",
            (_now(), chat_guid, chat_guid, _now()),
        )
        await db.commit()

    async with _QUEUE:
        _STATE["last_received"] = asyncio.get_running_loop().time()
        _STATE["items"].append({
            "external_id": external_id,
            "text": text or "",
            "images": images,
            "chat_guid": chat_guid or "",
            "reply_to": reply_to,
            "quote_text": quote_text,
        })
    _schedule()
    return {"ok": True, "queued": True}


def _note_lag(sent_at: str) -> None:
    if not sent_at:
        return
    try:
        stamp = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        lag = (datetime.now(timezone.utc) - stamp).total_seconds()
    except (ValueError, TypeError):
        return
    if lag > 30:
        logger.info("imessage_delivery_lag_s=%s", int(lag))


def _schedule() -> None:
    if not _STATE["auto_fire"]:
        return
    task = _STATE.get("task")
    if task and not task.done():
        return
    _STATE["task"] = asyncio.create_task(_sleep_then_fire())


async def _sleep_then_fire() -> None:
    try:
        await flush_pending()
    finally:
        if _STATE.get("task") is asyncio.current_task():
            _STATE["task"] = None
            if _STATE["items"]:
                _schedule()


async def flush_pending() -> None:
    # One consumer owns the queue throughout generation. Never remove messages
    # into a cancellable task waiting behind another turn.
    async with _LOCK:
        while True:
            account = await get_account()
            wait = max(2, min(10, int(account.get("merge_wait_seconds") or 4)))
            async with _QUEUE:
                if not _STATE["items"]:
                    return
                remaining = _STATE["last_received"] + wait - asyncio.get_running_loop().time()
                if not _STATE["auto_fire"] or remaining <= 0:
                    items = _STATE["items"]
                    _STATE["items"] = []
                else:
                    items = None
            if items is None:
                await asyncio.sleep(remaining)
                continue
            logger.info("imessage_burst_start count=%s", len(items))
            await _run_turn(items)


async def _reply_is_current() -> bool:
    async with _QUEUE:
        return not _STATE["items"]


async def _run_turn(items: list[dict]) -> None:
    merged = "\n".join(item["text"].strip() for item in items if item.get("text") and item["text"].strip()).strip()
    if not merged and not any(item.get("images") for item in items):
        return
    merged = merged or "[本轮通过 iMessage 发来图片]"
    chat_guid = next((item["chat_guid"] for item in reversed(items) if item.get("chat_guid")), "")
    ref_id = items[-1]["external_id"]
    account = await get_account()
    from app.services.chat_service import get_or_create_conversation, stream_chat, save_message

    conversation_id = await _latest_conversation_id()
    conversation_id = await get_or_create_conversation(conversation_id)
    await _enqueue(conversation_id, "read", "", ref_id=ref_id, chat_guid=chat_guid, delay_ms=0)
    await _enqueue(conversation_id, "typing_start", "", ref_id=ref_id, chat_guid=chat_guid, delay_ms=0)

    # Photo bursts retain their original messages, not an extra duplicate text
    # bubble. Each photo uses the existing authenticated web image history.
    has_images = any(item.get("images") for item in items)
    if has_images:
        for item in items:
            for index, image in enumerate(item.get("images") or [""]):
                message_id = await save_message(conversation_id, "user", item["text"] if index == 0 else "", image=image, channel="imessage")
                if index == 0:
                    await imessage_interactions.record_bubble(
                        external_id=item["external_id"], chat_guid=chat_guid,
                        conversation_id=conversation_id, message_id=message_id,
                        direction="inbound", body=item["text"] or "[图片]",
                        reply_to=item.get("reply_to", ""), quote_text=item.get("quote_text", ""))

    saved_ids = {}
    turn = {"chat_guid": chat_guid, "items": items}

    async def on_saved(role, message_id):
        saved_ids[role] = message_id
        if role == "user":
            for item in items:
                if item.get("images"):
                    continue
                await imessage_interactions.record_bubble(
                    external_id=item["external_id"], chat_guid=chat_guid,
                    conversation_id=conversation_id, message_id=message_id,
                    direction="inbound", body=item["text"], reply_to=item.get("reply_to", ""), quote_text=item.get("quote_text", ""))

    error_code = ""
    reaction_only = False
    async for event in stream_chat(
        conversation_id,
        merged,
        mode="daily",
        reply_style="split",
        channel="imessage",
        ingress_note=INGRESS_NOTE,
        push_reply=False,
        save_error_reply=False,
        reply_is_current=_reply_is_current,
        on_message_saved=on_saved, imessage_turn=turn,
        context_images=[image for item in items for image in item.get("images", [])] or None,
        persist_user=not has_images,
    ):
        if isinstance(event, dict) and event.get("type") == "reaction_only":
            reaction_only = True
        if isinstance(event, dict) and event.get("type") == "superseded":
            logger.info("imessage_reply_superseded")
            return
        if isinstance(event, dict) and event.get("type") == "error":
            error_code = event.get("code") or "error"

    if error_code and not await _reply_is_current():
        return
    if error_code:
        await _fail_turn(conversation_id, chat_guid, account, "这轮没有生成回复")
        return

    if reaction_only:
        for target, emoji in turn.get("reactions", {}).items():
            await _enqueue(conversation_id, "reaction", emoji, ref_id=target, chat_guid=chat_guid)
        await _enqueue(conversation_id, "typing_stop", "", chat_guid=chat_guid)
        return

    async with get_db() as db:
        async with db.execute("SELECT content FROM messages WHERE id=?", (saved_ids.get("assistant", ""),)) as cur:
            row = await cur.fetchone()
    reply = row["content"] if row else ""
    bubbles = sanitize_bubbles(reply)
    if not bubbles and not turn.get("generated_image"):
        await _fail_turn(conversation_id, chat_guid, account, "这轮没有可发送的文字")
        return

    for target, emoji in turn.get("reactions", {}).items():
        await _enqueue(conversation_id, "reaction", emoji, ref_id=target, chat_guid=chat_guid)
    if turn.get("generated_image"):
        image_id = await save_message(conversation_id, "assistant", "", image=turn["generated_image"], channel="imessage", image_kind=turn.get("image_kind", "photo"))
        await _enqueue(conversation_id, "image", "[图片]", message_id=image_id, chat_guid=chat_guid)
    per_char = int(account.get("typing_ms_per_char") or 45)
    for index, bubble in enumerate(bubbles):
        await _enqueue(
            conversation_id,
            "reply" if index == 0 and turn.get("reply_to") else "send",
            bubble,
            message_id=saved_ids.get("assistant", ""),
            ref_id=turn.get("reply_to") if index == 0 and turn.get("reply_to") else ref_id,
            chat_guid=chat_guid,
            delay_ms=bubble_delay_ms(bubble, per_char, first=index == 0),
        )
    await _enqueue(conversation_id, "typing_stop", "", ref_id=ref_id, chat_guid=chat_guid, delay_ms=0)


async def _fail_turn(conversation_id: str, chat_guid: str, account: dict, detail: str) -> None:
    await set_status(account.get("status") or "failed", detail)
    from app.services.chat_service import save_message

    if account.get("failure_phrase_enabled"):
        await save_message(conversation_id, "assistant", FAILURE_PHRASE, channel="imessage", display_mode="split")
        await _enqueue(conversation_id, "send", FAILURE_PHRASE, chat_guid=chat_guid, delay_ms=0)
    else:
        await save_message(
            conversation_id,
            "system",
            "iMessage 这轮没有发出去。原因记在 iMessage 连接的状态里。",
            channel="imessage",
        )
    await _enqueue(conversation_id, "typing_stop", "", chat_guid=chat_guid, delay_ms=0)
    logger.info("imessage_turn_failed")


async def deliver_proactive(conversation_id: str, content: str, thinking: str = "") -> int:
    """Store the nudge, and send it to iMessage when that door is selected."""
    from app.services.chat_service import save_message
    from app.services.push_service import send_push

    account = await get_account()
    bubbles = sanitize_bubbles(content)
    proactive_message_id = await save_message(
        conversation_id,
        "assistant",
        content.strip(),
        thinking=thinking,
        channel="imessage",
        display_mode="split",
    )
    if bubbles and account.get("enabled") and account.get("status") == "connected" and account.get("chat_guid"):
        per_char = int(account.get("typing_ms_per_char") or 45)
        chat_guid = account.get("chat_guid") or ""
        await _enqueue(conversation_id, "typing_start", "", chat_guid=chat_guid, delay_ms=0)
        for index, bubble in enumerate(bubbles):
            await _enqueue(
                conversation_id,
                "send",
                bubble,
                message_id=proactive_message_id,
                chat_guid=chat_guid,
                delay_ms=bubble_delay_ms(bubble, per_char, first=index == 0),
            )
        await _enqueue(conversation_id, "typing_stop", "", chat_guid=chat_guid, delay_ms=0)
        return len(bubbles)

    await set_status(account.get("status") or "failed", "主动消息没能发到 iMessage，已改用网页通知")
    preview = content[:60].split("\n")[0]
    try:
        await send_push(body=preview, tag="nudge")
    except Exception as exc:
        logger.warning("imessage_nudge_push_failed error_type=%s", type(exc).__name__)
    return max(len(bubbles), 1)


async def _latest_conversation_id() -> str | None:
    async with get_db() as db:
        async with db.execute("SELECT id FROM conversations ORDER BY updated_at DESC LIMIT 1") as cur:
            row = await cur.fetchone()
    return row["id"] if row else None


async def _enqueue(conversation_id: str, kind: str, body: str, *, ref_id: str = "", chat_guid: str = "", delay_ms: int = 0, message_id: str = "") -> str:
    item_id = str(uuid.uuid4())
    now = _now()
    async with get_db() as db:
        async with db.execute("SELECT COALESCE(MAX(sequence), 0) + 1 AS n FROM imessage_outbox") as cur:
            sequence = (await cur.fetchone())["n"]
        await db.execute(
            """INSERT INTO imessage_outbox
               (id, conversation_id, message_id, kind, body, ref_id, chat_guid, delay_ms, sequence, status, attempts, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)""",
            (item_id, conversation_id, message_id or None, kind, body, ref_id, chat_guid, int(delay_ms), sequence, now, now),
        )
        await db.commit()
    return item_id


async def pending_actions(limit: int = 20) -> list[dict]:
    async with get_db() as db:
        async with db.execute(
            """SELECT id, conversation_id, kind, body, ref_id, chat_guid, delay_ms, sequence, attempts
               FROM imessage_outbox WHERE status = 'pending'
               ORDER BY sequence ASC LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def ack_action(action_id: str, ok: bool, *, external_id: str = "") -> None:
    now = _now()
    async with get_db() as db:
        async with db.execute("SELECT * FROM imessage_outbox WHERE id = ?", (action_id,)) as cur:
            row = await cur.fetchone()
        if not row or row["status"] == "sent":
            return
        if ok:
            await db.execute(
                "UPDATE imessage_outbox SET status = 'sent', updated_at = ? WHERE id = ?",
                (now, action_id),
            )
            if row["kind"] in ("send", "reply", "image"):
                if external_id and row["message_id"]:
                    await db.execute("""INSERT INTO imessage_bubbles
                        (external_id, chat_guid, conversation_id, message_id, direction, body, reply_to)
                        VALUES (?, ?, ?, ?, 'outbound', ?, ?) ON CONFLICT(chat_guid,external_id) DO NOTHING""",
                        (external_id, row["chat_guid"], row["conversation_id"], row["message_id"], row["body"], row["ref_id"] if row["kind"] == "reply" else ""))
                await db.execute(
                    "UPDATE imessage_accounts SET last_outbound_at = ?, updated_at = ?, status = CASE WHEN enabled = 1 AND status IN ('failed', 'connecting', 'connected') THEN 'connected' ELSE status END, status_detail = CASE WHEN enabled = 1 AND status IN ('failed', 'connecting', 'connected') THEN '' ELSE status_detail END WHERE id = 1",
                    (now, now),
                )
            if row["kind"] == "reaction":
                await db.execute("""INSERT INTO imessage_reactions (chat_guid,target_id,actor,emoji)
                    VALUES (?,?,'assistant',?) ON CONFLICT(chat_guid,target_id,actor)
                    DO UPDATE SET emoji=excluded.emoji, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
                    (row["chat_guid"], row["ref_id"], row["body"]))
        else:
            attempts = int(row["attempts"]) + 1
            status = "pending" if attempts < 2 else "failed"
            await db.execute(
                "UPDATE imessage_outbox SET status = ?, attempts = ?, updated_at = ? WHERE id = ?",
                (status, attempts, now, action_id),
            )
        await db.commit()


async def mirror_saved_image(conversation_id: str, image_id: str) -> bool:
    """Queue a saved web image once, only while the configured line is live."""
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT enabled,status,chat_guid FROM imessage_accounts WHERE id=1") as cur:
            account = await cur.fetchone()
        if not account or not account["enabled"] or account["status"] != "connected" or not account["chat_guid"]:
            return False
        async with db.execute("SELECT 1 FROM messages WHERE id=? AND conversation_id=? AND role='assistant' AND image='file'", (image_id, conversation_id)) as cur:
            if not await cur.fetchone():
                return False
        async with db.execute("SELECT 1 FROM imessage_outbox WHERE message_id=? AND kind='image'", (image_id,)) as cur:
            if await cur.fetchone():
                return True
        now = _now()
        await db.execute("""INSERT INTO imessage_outbox
            (id,conversation_id,message_id,kind,body,ref_id,chat_guid,delay_ms,sequence,status,attempts,created_at,updated_at)
            VALUES (?,?,?,'image','[图片]','',?,0,(SELECT COALESCE(MAX(sequence),0)+1 FROM imessage_outbox),'pending',0,?,?)""",
            (str(uuid.uuid4()), conversation_id, image_id, account["chat_guid"], now, now))
        await db.commit()
    return True
