import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "attendance-ai-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL") or (
        "sqlite:///" + str(BASE_DIR / "attendance.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "uploads")
    FACE_DATASET_FOLDER = str(BASE_DIR / "static" / "face_dataset")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    JSON_SORT_KEYS = False
