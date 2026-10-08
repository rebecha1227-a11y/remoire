"""Import a UTF-8 original verbatim, without enabling it or calling a model."""
import argparse
import asyncio
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import database
from app.services import prompt_profile_service as profiles


async def import_original(source: Path):
    # read_bytes preserves CRLF and all whitespace in the source.
    content = source.read_bytes().decode("utf-8")
    if len(content) > profiles.MAX_CONTENT:
        raise ValueError("原稿超过 60000 字符，请分开保存")
    async with database.get_db() as db:
        await profiles.initialize(db)
    current = next(item for item in await profiles.list_profiles() if item["key"] == "original")
    if current["content"] == content:
        return current
    if current["content"]:
        raise ValueError("原稿资料已有内容；请在网页中编辑，本脚本不会覆盖")
    return await profiles.save_profile("original", content, False, current["version"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    database.DATABASE_PATH = str(args.database.resolve())
    if args.database.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = args.database.with_name(f"{args.database.stem}.before-profiles-{stamp}.db")
        with sqlite3.connect(args.database) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
        print("已通过 SQLite 在线备份保存导入前快照。")
    item = asyncio.run(import_original(args.source))
    print(f"原稿已保存，版本 {item['version']}；未用于模型生成。")
