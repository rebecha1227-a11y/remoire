from dotenv import load_dotenv
import os

load_dotenv()

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")
DEVICE_SECRET_KEY = os.getenv("DEVICE_SECRET_KEY", "")
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
