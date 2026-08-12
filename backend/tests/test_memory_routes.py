import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routers.memory import CreateRequest, create_memory


class MemoryRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_memory_normalizes_date_and_returns_service_result(self):
        request = CreateRequest(
            content="静儿生日",
            tags=["特殊日期"],
            layer="long",
            memory_type="date",
            event_date=date(2000, 4, 12),
        )
        service_result = {
            "memory": {"id": "memory-1", "content": "静儿生日", "event_date": "2000-04-12"},
            "associated": [],
        }

        with patch("app.routers.memory.memory_service.create_memory", AsyncMock(return_value=service_result)) as mocked:
            response = await create_memory(request, None)

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"], service_result)
        self.assertEqual(mocked.await_args.kwargs["event_date"], "2000-04-12")
        self.assertEqual(mocked.await_args.kwargs["memory_type"], "date")

    async def test_create_memory_rejects_duplicate_as_conflict(self):
        request = CreateRequest(content="已经存在", memory_type="date", event_date=date(2000, 1, 1))
        duplicate = {"memory": {"id": None, "duplicate": True}, "associated": []}

        with patch("app.routers.memory.memory_service.create_memory", AsyncMock(return_value=duplicate)):
            with self.assertRaises(HTTPException) as caught:
                await create_memory(request, None)

        self.assertEqual(caught.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
