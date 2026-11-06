"""Environment-backed application configuration."""
import os
import secrets
import warnings
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


class Settings:
    ENVIRONMENT = os.getenv("APP_ENV", "development").strip().lower()
    SECRET_KEY = os.getenv("JWT_SECRET", "").strip()
    if len(SECRET_KEY) < 32 or SECRET_KEY.startswith("replace-with-"):
        if ENVIRONMENT == "production":
            raise RuntimeError("Set a random JWT_SECRET of at least 32 characters in backend/.env")
        SECRET_KEY = secrets.token_hex(32)
        warnings.warn("JWT_SECRET is not configured; a temporary development key was generated. Set it in backend/.env to preserve sessions across restarts.", RuntimeWarning)
    JWT_ISSUER = os.getenv("JWT_ISSUER", "gradpath-api")
    JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "gradpath-web")
    JWT_TTL_SECONDS = int(os.getenv("JWT_TTL_SECONDS", "3600"))
    if not 300 <= JWT_TTL_SECONDS <= 86400:
        raise RuntimeError("JWT_TTL_SECONDS must be between 300 and 86400")
    MONGO_URI = os.getenv("MONGO_URI", "").strip()
    MONGO_DB = os.getenv("MONGO_DB", "placement_prediction")
    MONGO_SERVER_SELECTION_TIMEOUT_MS = int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "2500"))
    DATA_DIR = BACKEND_ROOT / "data"
    MODEL_PATH = DATA_DIR / "model.joblib"
    STUDENTS_PATH = DATA_DIR / "students.json"
    USERS_PATH = DATA_DIR / "users.json"
    ADMIN_BOOTSTRAP_KEY = os.getenv("ADMIN_BOOTSTRAP_KEY", "").strip()
    if ADMIN_BOOTSTRAP_KEY.startswith("replace-with-"):
        ADMIN_BOOTSTRAP_KEY = ""
    if ENVIRONMENT == "production" and len(ADMIN_BOOTSTRAP_KEY) < 32:
        raise RuntimeError("Set a random ADMIN_BOOTSTRAP_KEY of at least 32 characters in backend/.env")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    JSON_SORT_KEYS = False
    FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if origin.strip()]
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    if ENVIRONMENT == "production" and RATELIMIT_STORAGE_URI.startswith("memory://"):
        raise RuntimeError("Configure a shared Redis RATELIMIT_STORAGE_URI for production deployments")
    RATELIMIT_HEADERS_ENABLED = True
