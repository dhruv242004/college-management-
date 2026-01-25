"""Application configuration."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "college-mgmt-secret-key-change-in-production"
    SESSION_TYPE = "filesystem"
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # MySQL
    MYSQL_HOST = os.environ.get("MYSQL_HOST") or "localhost"
    MYSQL_USER = os.environ.get("MYSQL_USER") or "root"
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD") or ""
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE") or "college_management"
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT") or 3306)

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB for photos
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


config = Config()
