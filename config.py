"""Application configuration."""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Only load .env if NOT running on Render (production)
if os.environ.get("FLASK_ENV") != "production":
    load_dotenv(os.path.join(BASE_DIR, '.env'))


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

config = Config()
