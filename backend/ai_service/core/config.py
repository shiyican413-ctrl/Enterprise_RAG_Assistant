import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
KNOWLEDGE_DIR = DATA_DIR / "knowledge_base"
INDEX_FILE = KNOWLEDGE_DIR / "chunks.json"
HISTORY_FILE = KNOWLEDGE_DIR / "history.json"
USERS_FILE = KNOWLEDGE_DIR / "users.json"
TENANTS_FILE = KNOWLEDGE_DIR / "tenants.json"


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
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-before-production").strip()
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
INITIAL_ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@example.com").strip().lower()
INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "Admin123!")
INITIAL_ADMIN_NAME = os.getenv("INITIAL_ADMIN_NAME", "系统管理员").strip()
DEFAULT_TENANT_ID = os.getenv(
    "DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001"
).strip()
DEFAULT_TENANT_NAME = os.getenv("DEFAULT_TENANT_NAME", "默认企业").strip()
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

BAILIAN_CHAT_URL = os.getenv(
    "BAILIAN_CHAT_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
)
BAILIAN_FAST_MODEL = os.getenv("BAILIAN_FAST_MODEL", "qwen3.5-flash")
BAILIAN_THINKING_MODEL = os.getenv("BAILIAN_THINKING_MODEL", "qwen3.7-plus")
BAILIAN_THINKING_BUDGET = int(os.getenv("BAILIAN_THINKING_BUDGET", "8192"))
BAILIAN_RERANK_MODEL = os.getenv("BAILIAN_RERANK_MODEL", "qwen3-rerank")
CHAT_TIMEOUT_SECONDS = float(os.getenv("CHAT_TIMEOUT_SECONDS", "60"))

# --- Agent Runtime controls ---------------------------------------------------
# Deterministic knobs owned by the Runtime layer (ExecutorService), never by the
# LLM. See docs/agent改进.md §4: "代码负责：执行、限制、校验、记录、重试".
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "4"))
AGENT_TOTAL_TIMEOUT_SECONDS = float(os.getenv("AGENT_TOTAL_TIMEOUT_SECONDS", "120"))
AGENT_RETRY_ATTEMPTS = int(os.getenv("AGENT_RETRY_ATTEMPTS", "0"))
