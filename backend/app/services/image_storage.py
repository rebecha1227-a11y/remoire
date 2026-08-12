import base64
import binascii
import os
from pathlib import Path
from uuid import UUID
from app.config import BASE_DIR

IMAGES_DIR = Path(BASE_DIR) / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_ENCODED_IMAGE_CHARS = (MAX_IMAGE_BYTES * 4 // 3) + 256
_SUPPORTED_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


class InvalidImageError(ValueError):
    pass


def _detect_mime(data: bytes) -> str | None:
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if data[:2] == b'\xff\xd8':
        return "image/jpeg"
    if data[:4] == b'GIF8':
        return "image/gif"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp"
    return None


def decode_image(image_data: str) -> tuple[bytes, str]:
    if not image_data or len(image_data) > MAX_ENCODED_IMAGE_CHARS:
        raise InvalidImageError("图片不能超过 8MB")

    declared_mime = None
    encoded = image_data
    if image_data.startswith("data:"):
        try:
            header, encoded = image_data.split(",", 1)
        except ValueError as exc:
            raise InvalidImageError("图片数据格式无效") from exc
        if not header.endswith(";base64"):
            raise InvalidImageError("图片必须使用 Base64 编码")
        declared_mime = header[5:-7].lower()
        if declared_mime == "image/jpg":
            declared_mime = "image/jpeg"
        if declared_mime not in _SUPPORTED_MIME_TYPES:
            raise InvalidImageError("只支持 PNG、JPEG、GIF 或 WebP 图片")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidImageError("图片 Base64 数据无效") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise InvalidImageError("图片不能超过 8MB")

    detected_mime = _detect_mime(raw)
    if not detected_mime:
        raise InvalidImageError("无法识别图片格式")
    if declared_mime and declared_mime != detected_mime:
        raise InvalidImageError("图片声明格式与实际内容不一致")
    return raw, detected_mime


def _image_path(message_id: str) -> Path:
    try:
        normalized = str(UUID(message_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidImageError("图片标识无效") from exc
    if normalized != message_id:
        raise InvalidImageError("图片标识无效")
    return IMAGES_DIR / normalized


def save_image(message_id: str, image_data: str) -> bool:
    raw, _ = decode_image(image_data)
    path = _image_path(message_id)
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_bytes(raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def get_image(message_id: str) -> tuple[bytes, str] | None:
    try:
        path = _image_path(message_id)
    except InvalidImageError:
        return None
    if not path.exists():
        return None
    raw = path.read_bytes()
    mime = _detect_mime(raw)
    return (raw, mime) if mime else None


def delete_image(message_id: str) -> None:
    try:
        _image_path(message_id).unlink(missing_ok=True)
    except InvalidImageError:
        return
