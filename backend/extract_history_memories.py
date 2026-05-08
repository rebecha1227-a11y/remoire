"""
从导入的历史聊天中批量提取记忆候选。
每 20 条消息分一组发给 AI 分析，提取出值得记住的信息。
"""
import asyncio
import json
from app.database import get_db, init_db
from app.services.memory_service import extract_candidates

BATCH_SIZE = 20


async def main():
    await init_db()

    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM conversations ORDER BY created_at"
        ) as cur:
            convs = await cur.fetchall()

    print(f"共 {len(convs)} 个对话，开始提取记忆...\n")

    total_candidates = 0

    for i, conv in enumerate(convs):
        conv_id = conv["id"]

        async with get_db() as db:
            async with db.execute(
                "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at",
                (conv_id,),
            ) as cur:
                msgs = await cur.fetchall()

        messages = [{"role": r["role"], "content": r["content"]} for r in msgs]

        if len(messages) < 3:
            continue

        batches = [messages[j:j + BATCH_SIZE] for j in range(0, len(messages), BATCH_SIZE)]

        conv_count = 0
        for batch in batches:
            try:
                candidates = await extract_candidates(conv_id, batch)
                conv_count += len(candidates)
                for c in candidates:
                    print(f"  💡 {c['content']}")
            except Exception as e:
                print(f"  ⚠️ 批次提取失败: {e}")
            await asyncio.sleep(1)

        total_candidates += conv_count
        print(f"[{i+1}/{len(convs)}] 对话 {conv_id[:8]}... → {conv_count} 条候选")

    print(f"\n✅ 提取完成！共 {total_candidates} 条记忆候选，等待确认。")
    print("用 GET /api/memory/candidates 查看，用 POST /api/memory/candidates/{id}/accept 确认。")


if __name__ == "__main__":
    asyncio.run(main())
