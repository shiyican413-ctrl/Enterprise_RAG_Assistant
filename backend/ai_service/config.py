import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
KNOWLEDGE_DIR = DATA_DIR / "knowledge_base"
INDEX_FILE = KNOWLEDGE_DIR / "chunks.json"
HISTORY_FILE = KNOWLEDGE_DIR / "history.json"


def _load_local_env() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()

APP_NAME = "Enterprise RAG Assistant AI Service"
APP_VERSION = "0.1.0"

CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
TOP_K = 4
VECTOR_SCORE_THRESHOLD = float(os.getenv("VECTOR_SCORE_THRESHOLD", "0.20"))

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

SUPPORTED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}

GLM_API_KEY = os.getenv("GLM_API_KEY", "").strip()
GLM_EMBEDDING_URL = os.getenv(
    "GLM_EMBEDDING_URL",
    "https://open.bigmodel.cn/api/paas/v4/embeddings",
)
GLM_EMBEDDING_MODEL = os.getenv("GLM_EMBEDDING_MODEL", "embedding-3")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))

GLM_CHAT_URL = os.getenv(
    "GLM_CHAT_URL",
    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
)
GLM_FAST_MODEL = os.getenv("GLM_FAST_MODEL", "GLM-4V-Flash")
GLM_THINKING_MODEL = os.getenv("GLM_THINKING_MODEL", "GLM-4.1V-Thinking-Flash")
CHAT_TIMEOUT_SECONDS = float(os.getenv("CHAT_TIMEOUT_SECONDS", "60"))
