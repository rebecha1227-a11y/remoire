import unittest

from app.services import model_settings_service as svc


class ImageProviderTests(unittest.TestCase):
    def test_normalize_legacy_image_providers(self):
        self.assertEqual(svc.normalize_provider("openai-image"), "image")
        self.assertEqual(svc.normalize_provider("gemini-image"), "image")
        self.assertEqual(svc.normalize_provider("openai-compatible"), "openai-compatible")

    def test_resolve_wire_from_host_and_model(self):
        self.assertEqual(
            svc.resolve_image_wire_protocol("image", "https://api.openai.com/v1", "gpt-image-1"),
            "openai-image",
        )
        self.assertEqual(
            svc.resolve_image_wire_protocol(
                "image",
                "https://generativelanguage.googleapis.com/v1beta",
                "gemini-2.5-flash-image",
            ),
            "gemini-image",
        )
        self.assertEqual(svc.resolve_image_wire_protocol("gemini-image", "https://relay.example/v1", "x"), "gemini-image")


if __name__ == "__main__":
    unittest.main()
