import base64
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.routers.chat import SendRequest
from app.services import image_storage


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class ImageStorageTests(unittest.TestCase):
    def test_valid_image_round_trip_uses_uuid_scoped_file(self):
        message_id = str(uuid.uuid4())
        payload = f"data:image/png;base64,{base64.b64encode(ONE_PIXEL_PNG).decode('ascii')}"
        with tempfile.TemporaryDirectory() as tempdir, patch.object(image_storage, "IMAGES_DIR", Path(tempdir)):
            self.assertTrue(image_storage.save_image(message_id, payload))
            restored = image_storage.get_image(message_id)

        self.assertEqual(restored, (ONE_PIXEL_PNG, "image/png"))

    def test_rejects_invalid_base64_and_mime_spoofing(self):
        with self.assertRaises(image_storage.InvalidImageError):
            image_storage.decode_image("data:image/png;base64,not-valid-@@")

        jpeg_claim = f"data:image/jpeg;base64,{base64.b64encode(ONE_PIXEL_PNG).decode('ascii')}"
        with self.assertRaises(image_storage.InvalidImageError):
            image_storage.decode_image(jpeg_claim)

    def test_rejects_oversized_payload_before_decoding(self):
        payload = "A" * (image_storage.MAX_ENCODED_IMAGE_CHARS + 1)
        with self.assertRaises(image_storage.InvalidImageError):
            image_storage.decode_image(payload)

    def test_image_lookup_rejects_non_uuid_paths(self):
        with tempfile.TemporaryDirectory() as tempdir, patch.object(image_storage, "IMAGES_DIR", Path(tempdir)):
            self.assertIsNone(image_storage.get_image("../private-key"))

    def test_delete_image_removes_only_uuid_scoped_file(self):
        message_id = str(uuid.uuid4())
        payload = f"data:image/png;base64,{base64.b64encode(ONE_PIXEL_PNG).decode('ascii')}"
        with tempfile.TemporaryDirectory() as tempdir, patch.object(image_storage, "IMAGES_DIR", Path(tempdir)):
            image_storage.save_image(message_id, payload)
            image_storage.delete_image(message_id)
            self.assertIsNone(image_storage.get_image(message_id))
            image_storage.delete_image("../outside")

    def test_chat_request_validation_blocks_invalid_image_and_parameters(self):
        with self.assertRaises(ValidationError):
            SendRequest(message="hello", image="data:image/svg+xml;base64,PHN2Zz4=")
        with self.assertRaises(ValidationError):
            SendRequest(message="hello", mode="unknown")
        with self.assertRaises(ValidationError):
            SendRequest(message="")


if __name__ == "__main__":
    unittest.main()
