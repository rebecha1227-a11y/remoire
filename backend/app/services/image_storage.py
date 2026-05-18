import base64
import os
from pathlib import Path
from app.config import BASE_DIR

IMAGES_DIR = Path(BASE_DIR) / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _detect_mime(data: bytes) -> str:
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if data[:2] == b'\xff\xd8':
        return "image/jpeg"
    if data[:4] == b'GIF8':
        return "image/gif"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp"
    return "image/jpeg"


def save_image(message_id: str, image_data: str) -> bool:
    try:
        if image_data.startswith("data:"):
            _, b64 = image_data.split(",", 1)
        else:
            b64 = image_data
        raw = base64.b64decode(b64)
        (IMAGES_DIR / message_id).write_bytes(raw)
        return True
    except Exception:
        return False


def get_image(message_id: str) -> tuple[bytes, str] | None:
    path = IMAGES_DIR / message_id
    if not path.exists():
        return None
    raw = path.read_bytes()
    return raw, _detect_mime(raw)
