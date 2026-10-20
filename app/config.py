"""Application configuration, driven by environment variables (see .env.example)."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Real environment variables always win over values from .env.
load_dotenv(BASE_DIR / ".env")

INSECURE_SECRET_KEYS = {
    "",
    "change-me",
    "changeme",
    "dev-only-not-for-production",
    "your-secret-key-change-in-production",
}


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_list(name):
    raw = os.environ.get(name, "")
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def normalize_database_url(url):
    # Some hosts still hand out postgres:// URLs, which SQLAlchemy 2.x rejects.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


class Config:
    APP_ENV = "production"
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    SITE_NAME = os.environ.get("SITE_NAME", "Судалгааны систем")
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Ulaanbaatar")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    PAGE_SIZE = 20

    # Database
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get("DATABASE_URL", "sqlite:///surveys.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Sessions and cookies
    SESSION_COOKIE_NAME = "survey_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=env_int("SESSION_LIFETIME_MINUTES", 120))

    # CSRF: tokens stay valid for 8 hours so respondents don't lose a long form.
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 8

    # Reject oversized request bodies (JSON uploads are the largest legitimate payload).
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    SEND_FILE_MAX_AGE_DEFAULT = timedelta(days=7)

    # Authentication
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    ADMIN_EMAILS = env_list("ADMIN_EMAILS")

    # Reverse proxy / rate limiting
    TRUSTED_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", 0)
    RATELIMIT_ENABLED = env_bool("RATELIMIT_ENABLED", True)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "10 per minute")
    SURVEY_RATE_LIMIT = os.environ.get("SURVEY_RATE_LIMIT", "100 per hour")


class DevelopmentConfig(Config):
    APP_ENV = "development"
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-not-for-production"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)


class ProductionConfig(Config):
    APP_ENV = "production"


class TestingConfig(Config):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "testing-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    ADMIN_EMAILS = []
    GOOGLE_CLIENT_ID = ""
    GOOGLE_CLIENT_SECRET = ""
    TRUSTED_PROXY_COUNT = 0


CONFIGS = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
}


def get_config(name=None):
    # Default to production so a forgotten APP_ENV fails closed (SECRET_KEY check) rather than open.
    key = (name or os.environ.get("APP_ENV") or "production").strip().lower()
    try:
        return CONFIGS[key]
    except KeyError:
        raise ValueError(f"Unknown APP_ENV {key!r}; use one of: development, production, testing") from None
