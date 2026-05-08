import json
import asyncio
import uuid
from datetime import datetime
from app.database import get_db, init_db

CLEAN_FILE = "../Connie 聊天记录备份/conversations_clean.json"

async def import_conversations():
    await init_db()

    with open(CLEAN_FILE, encoding="utf-8") as f:
        data = json.load(f)

    total_convs = 0
    total_msgs = 0

    async with get_db() as db:
        for conv in data:
            old_id = conv["uuid"]
            conv_id = str(uuid.uuid4())
            created = conv["created_at"]
            updated = conv["updated_at"]

            msgs = conv.get("chat_messages", [])
            if not msgs:
                continue

            first_human = ""
            for m in msgs:
                if m.get("sender") == "human" and m.get("text", "").strip():
                    first_human = m["text"].strip()[:30]
                    break
            title = first_human or "导入的对话"

            await db.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conv_id, title, created, updated),
            )
            total_convs += 1

            for m in msgs:
                text = (m.get("text") or "").strip()
                if not text:
                    continue

                role = "user" if m["sender"] == "human" else "assistant"
                msg_created = m.get("created_at", created)

                await db.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, channel, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), conv_id, role, text, "claude.ai", msg_created),
                )
                total_msgs += 1

        await db.commit()

    print(f"✅ 导入完成: {total_convs} 个对话, {total_msgs} 条消息")

if __name__ == "__main__":
    asyncio.run(import_conversations())
