import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app import database
from app.routers.diary import DiaryCreate, InteractionCreate
from app.routers.memory import RecallRequest, UpdateRequest
from app.routers.push import SubscribeRequest
from app.routers.reminder import CreateRequest as ReminderCreateRequest
from app.routers.settings import ModelProbeRequest, ProactiveSettingsRequest
from app.routers.signal import AppEventRequest, DeviceSnapshotRequest
from app.services import reminder_service


class RequestBoundaryTests(unittest.TestCase):
    def test_rejects_invalid_reminder_dates_and_oversized_content(self):
        with self.assertRaises(ValidationError):
            ReminderCreateRequest(content="提醒", remind_at="2026-99-99 25:90")
        with self.assertRaises(ValidationError):
            ReminderCreateRequest(content="x" * 1001, remind_at="2026-08-12 09:30")

    def test_diary_and_memory_inputs_have_explicit_bounds(self):
        with self.assertRaises(ValidationError):
            DiaryCreate(content="", author="jinger")
        with self.assertRaises(ValidationError):
            InteractionCreate(actor="connie", type="comment", content="伪造身份")
        with self.assertRaises(ValidationError):
            RecallRequest(query="记忆", limit=100000)
        with self.assertRaises(ValidationError):
            UpdateRequest(content="记忆", valence=2.0)

    def test_settings_reject_unknown_or_unbounded_values(self):
        with self.assertRaises(ValidationError):
            ProactiveSettingsRequest(max_daily=1000)
        with self.assertRaises(ValidationError):
            ProactiveSettingsRequest(types_json='{"care":true,"unknown":true}')
        with self.assertRaises(ValidationError):
            ModelProbeRequest(api_key="secret", base_url="https://example.com", unexpected=True)

    def test_signal_and_push_inputs_reject_impossible_values(self):
        with self.assertRaises(ValidationError):
            DeviceSnapshotRequest(latitude=120)
        with self.assertRaises(ValidationError):
            AppEventRequest(app_name="Safari", event_type="execute")
        with self.assertRaises(ValidationError):
            SubscribeRequest(endpoint="http://example.com/push", p256dh="key", auth="auth")


class ReminderPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_path = database.DATABASE_PATH
        database.DATABASE_PATH = str(Path(self.tempdir.name) / "request-boundaries.db")
        await database.init_db()

    async def asyncTearDown(self):
        database.DATABASE_PATH = self.original_path
        self.tempdir.cleanup()

    async def test_urgent_flag_survives_database_round_trip(self):
        created = await reminder_service.create_reminder(
            content="立刻处理",
            remind_at="2026-08-12 09:30",
            urgent=True,
        )
        listed = await reminder_service.list_reminders(limit=10)

        self.assertTrue(created["urgent"])
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["urgent"], 1)


if __name__ == "__main__":
    unittest.main()
