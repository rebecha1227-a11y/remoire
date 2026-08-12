import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app import database
from app.routers.diary import DiaryCreate, DiaryLockUpdate, InteractionCreate
from app.services import diary_interaction_service, diary_service
from app.services.diary_pin import verify_pin


class DiaryPrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_path = database.DATABASE_PATH
        database.DATABASE_PATH = str(Path(self.tempdir.name) / "diary-privacy.db")
        await database.init_db()

    async def asyncTearDown(self):
        database.DATABASE_PATH = self.original_path
        self.tempdir.cleanup()

    async def test_locked_diary_is_redacted_until_server_verifies_pin(self):
        created = await diary_service.create_diary(
            title="只给自己",
            content="不会随列表响应下发的正文",
            author="jinger",
            locked=True,
            pin="4826",
        )

        listed = await diary_service.list_diaries(
            author="jinger",
            include_locked_content=False,
        )
        wrong = await diary_interaction_service.verify_diary_pin(created["id"], "0000")
        verified = await diary_interaction_service.verify_diary_pin(created["id"], "4826")

        self.assertEqual(listed[0]["content"], "")
        self.assertIsNone(listed[0]["pin"])
        self.assertIsNone(wrong)
        self.assertEqual(verified["content"], "不会随列表响应下发的正文")
        self.assertNotIn("pin_hash", created)

        async with database.get_db() as db:
            async with db.execute(
                "SELECT pin, pin_hash FROM diary_entries WHERE id = ?",
                (created["id"],),
            ) as cursor:
                stored = await cursor.fetchone()
        self.assertIsNone(stored["pin"])
        self.assertTrue(verify_pin("4826", stored["pin_hash"]))
        self.assertNotIn("4826", stored["pin_hash"])

    async def test_startup_migrates_legacy_plaintext_pin(self):
        async with database.get_db() as db:
            await db.execute(
                """INSERT INTO diary_entries
                   (id, title, content, author, locked, pin, created_at, updated_at)
                   VALUES ('legacy', '旧日记', '正文', 'jinger', 1, '1234', 'now', 'now')"""
            )
            await db.commit()

        await database.init_db()
        async with database.get_db() as db:
            async with db.execute(
                "SELECT pin, pin_hash FROM diary_entries WHERE id = 'legacy'"
            ) as cursor:
                stored = await cursor.fetchone()

        self.assertIsNone(stored["pin"])
        self.assertTrue(verify_pin("1234", stored["pin_hash"]))

    def test_public_diary_requests_cannot_impersonate_connie(self):
        with self.assertRaises(ValidationError):
            DiaryCreate(content="伪造日记", author="connie")
        with self.assertRaises(ValidationError):
            InteractionCreate(actor="connie", type="comment", content="伪造回复")
        with self.assertRaises(ValidationError):
            DiaryLockUpdate(locked=False, pin="1234", actor="connie")
        with self.assertRaises(ValidationError):
            DiaryLockUpdate(locked=False)
        with self.assertRaises(ValidationError):
            DiaryCreate(content="缺少密码", author="jinger", locked=True)


if __name__ == "__main__":
    unittest.main()
