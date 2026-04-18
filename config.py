"""Application configuration."""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _env_strip(val, default=""):
    """Strip whitespace, UTF-8 BOM, and wrapping quotes from env values."""
    if val is None:
        return default
    s = str(val).strip().strip("\ufeff").strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    return s


# Load project .env when the file exists (fixes local dev if the shell has
# FLASK_ENV=production set globally, which would otherwise skip loading).
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.isfile(_env_path):
    load_dotenv(_env_path, override=True)
elif os.environ.get("FLASK_ENV") != "production":
    load_dotenv(_env_path, override=True)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "college-mgmt-secret-key-change-in-production"
    SESSION_TYPE = "filesystem"
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Database
    # Render's PostgreSQL provides DATABASE_URL
    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    # Fallback MySQL for local
    MYSQL_HOST = os.environ.get("MYSQL_HOST") or "localhost"
    MYSQL_USER = os.environ.get("MYSQL_USER") or "root"
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD") or ""
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE") or "college_management"
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT") or 3306)

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB for photos
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

    BASE_URL = os.environ.get("BASE_URL") or "http://localhost:5000"

    # Razorpay — set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env (never hardcode keys here)
    RAZORPAY_KEY_ID = _env_strip(os.environ.get("RAZORPAY_KEY_ID"))
    RAZORPAY_KEY_SECRET = _env_strip(os.environ.get("RAZORPAY_KEY_SECRET"))

config = Config()
