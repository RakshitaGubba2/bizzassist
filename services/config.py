"""Single configuration source for BizAssist AI."""
import os
from pathlib import Path

NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "google/gemma-4-31b-it"
DEFAULT_LANGUAGE = "en"
SQLITE_TIMEOUT_SECONDS = 30
TRANSLATION_BATCH_SIZE = 8
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database.db"


def load_flask_config():
    return {
        "NVIDIA_NIM_API_KEY": os.environ.get("NVIDIA_NIM_API_KEY", "").strip(),
        "NVIDIA_NIM_MODEL": os.environ.get("NVIDIA_NIM_MODEL", DEFAULT_MODEL).strip(),
        "LANGUAGE_DEFAULT": DEFAULT_LANGUAGE,
        "SQLITE_TIMEOUT_SECONDS": SQLITE_TIMEOUT_SECONDS,
        "TRANSLATION_BATCH_SIZE": TRANSLATION_BATCH_SIZE,
        "DATABASE_PATH": str(DATABASE_PATH),
    }
