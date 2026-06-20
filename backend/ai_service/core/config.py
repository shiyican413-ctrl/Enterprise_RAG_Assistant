import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[3]
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
VECTOR_STORE_BACKEND = os.getenv("VECTOR_STORE_BACKEND", "milvus").strip().lower()
MILVUS_URI = os.getenv("MILVUS_URI", "http://127.0.0.1:19530").strip()
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "").strip()
MILVUS_DB_NAME = os.getenv("MILVUS_DB_NAME", "").strip()
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "enterprise_rag_chunks").strip()

SUPPORTED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}

DASHSCOPE_API_KEY = (
    os.getenv("DASHSCOPE_API_KEY")
    or os.getenv("BAILIAN_API_KEY")
    or os.getenv("QWEN_API_KEY")
    or ""
).strip()
BAILIAN_EMBEDDING_URL = os.getenv(
    "BAILIAN_EMBEDDING_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
)
BAILIAN_EMBEDDING_MODEL = os.getenv("BAILIAN_EMBEDDING_MODEL", "text-embedding-v4")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "2048"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))

ARK_API_KEY = (
    os.getenv("ARK_API_KEY")
    or os.getenv("DOUBAO_API_KEY")
    or ""
).strip()
ARK_CHAT_URL = os.getenv(
    "ARK_CHAT_URL",
    "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
)
DOUBAO_FAST_MODEL = os.getenv("DOUBAO_FAST_MODEL", "doubao-seed-2-0-lite-260428")
DOUBAO_THINKING_MODEL = os.getenv(
    "DOUBAO_THINKING_MODEL",
    "doubao-seed-2-0-lite-260428",
)
CHAT_TIMEOUT_SECONDS = float(os.getenv("CHAT_TIMEOUT_SECONDS", "60"))
