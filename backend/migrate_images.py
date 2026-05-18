"""
迁移脚本：把 messages 表里的 base64 图片提取到 data/images/ 目录，
DB 的 image 字段改为 "file" 标记。

用法（在服务器上）：
  cd /opt/remoire/backend
  ./venv/bin/python migrate_images.py
"""
import sqlite3
import base64
import os
from pathlib import Path

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "remoire.db"))
IMAGES_DIR = Path(os.path.dirname(__file__)) / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT id, image FROM messages WHERE image IS NOT NULL AND image != '' AND image != 'file'"
    )
    rows = cursor.fetchall()
    print(f"找到 {len(rows)} 条带图片的消息")

    migrated = 0
    for row in rows:
        msg_id = row["id"]
        image_data = row["image"]
        try:
            if image_data.startswith("data:"):
                _, b64 = image_data.split(",", 1)
            else:
                b64 = image_data
            raw = base64.b64decode(b64)
            (IMAGES_DIR / msg_id).write_bytes(raw)
            conn.execute("UPDATE messages SET image = 'file' WHERE id = ?", (msg_id,))
            migrated += 1
        except Exception as e:
            print(f"  跳过 {msg_id}: {e}")

    conn.commit()
    conn.close()
    print(f"迁移完成：{migrated}/{len(rows)} 张图片已转移到文件系统")

    if migrated > 0:
        print("建议运行 VACUUM 压缩数据库：")
        print(f"  sqlite3 {DB_PATH} 'VACUUM;'")
        print("  或用 Python: conn.execute('VACUUM')")

if __name__ == "__main__":
    migrate()
