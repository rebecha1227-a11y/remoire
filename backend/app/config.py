from dotenv import load_dotenv
import os

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")
DEVICE_SECRET_KEY = os.getenv("DEVICE_SECRET_KEY", "")
MCP_API_TOKEN_SHA256 = os.getenv("MCP_API_TOKEN_SHA256", "").strip().lower()
MODEL_SECRET_ENCRYPTION_KEYS = _env_list("MODEL_SECRET_ENCRYPTION_KEYS", "")
APP_USERNAME = os.getenv("APP_USERNAME", "connie")
APP_PASSWORD_HASH = os.getenv("APP_PASSWORD_HASH", "")
MODEL_SECRET_ENCRYPTION_REQUIRED = _env_bool(
    "MODEL_SECRET_ENCRYPTION_REQUIRED",
    bool(APP_PASSWORD_HASH),
)
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "remoire_session")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "remoire_csrf")
SESSION_TTL_DAYS = max(1, int(os.getenv("SESSION_TTL_DAYS", "30")))
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
ALLOW_LEGACY_BEARER = _env_bool("ALLOW_LEGACY_BEARER", False)
TRUSTED_ORIGINS = _env_list(
    "TRUSTED_ORIGINS",
    "https://remoire.cc,http://localhost:5173,http://127.0.0.1:5173",
)
ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    "remoire.cc,www.remoire.cc,localhost,127.0.0.1,testserver",
)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "data", "remoire.db"))
UPLOADS_PATH = os.getenv("UPLOADS_PATH", os.path.join(BASE_DIR, "uploads"))

DAILY_API_BASE = os.getenv("DAILY_API_BASE", "")
DAILY_API_KEY = os.getenv("DAILY_API_KEY", "")
DAILY_MODEL_ID = os.getenv("DAILY_MODEL_ID", "")

QWEATHER_API_KEY = os.getenv("QWEATHER_API_KEY", "")
QWEATHER_API_HOST = os.getenv("QWEATHER_API_HOST", "")
QWEATHER_LOCATION = os.getenv("QWEATHER_LOCATION", "113.53,22.80")

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_CONTACT = os.getenv("VAPID_CONTACT", "mailto:rebecha@remoire.cc")

EMBEDDING_API_BASE = os.getenv("EMBEDDING_API_BASE", "")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "")
