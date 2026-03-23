"""Application configuration."""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    DATABASE_PATH = os.path.join(BASE_DIR, "instance", "radio.db")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB max upload
    ALLOWED_EXTENSIONS = {"mp3"}
    # Default admin credentials (change in production)
    DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    # Stream settings
    STREAM_CHUNK_SIZE = 4096  # bytes per chunk sent to listeners
    STREAM_BITRATE = 128  # kbps for streaming
