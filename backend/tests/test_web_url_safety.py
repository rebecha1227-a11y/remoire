import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import web_service


class WebUrlSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_http_and_private_targets(self):
        for url in (
            "file:///etc/passwd",
            "http://127.0.0.1:8000/private",
            "http://[::1]/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://user:password@example.com/private",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                await web_service.validate_public_web_url(url)

    async def test_rejects_domains_resolving_to_private_addresses(self):
        private_result = [
            (2, 1, 6, "", ("10.0.0.7", 443)),
        ]
        with patch("app.services.web_service.socket.getaddrinfo", return_value=private_result):
            with self.assertRaises(ValueError):
                await web_service.validate_public_web_url("https://internal.example/path")

    async def test_accepts_public_https_target(self):
        public_result = [
            (2, 1, 6, "", ("93.184.216.34", 443)),
        ]
        with patch("app.services.web_service.socket.getaddrinfo", return_value=public_result):
            target = await web_service.validate_public_web_url("https://example.com/article")
        self.assertEqual(target, "https://example.com/article")

    async def test_safe_navigation_rechecks_redirect_destination(self):
        page = AsyncMock()
        page.url = "https://example.com"
        route = AsyncMock()
        route.request = MagicMock()
        route.request.is_navigation_request.return_value = True
        route.request.url = "http://127.0.0.1/admin"
        async def trigger_route(*_args, **_kwargs):
            handler = page.route.await_args.args[1]
            await handler(route)
            raise RuntimeError("navigation aborted")
        page.goto.side_effect = trigger_route
        public_result = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with patch("app.services.web_service.socket.getaddrinfo", return_value=public_result):
            with self.assertRaises(ValueError):
                await web_service._safe_page_goto(page, "https://example.com")
        page.goto.assert_awaited_once()
        route.abort.assert_awaited_once_with("blockedbyclient")
        page.unroute.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
