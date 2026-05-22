import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
KNOWLEDGE_DIR = DATA_DIR / "knowledge_base"
INDEX_FILE = KNOWLEDGE_DIR / "chunks.json"
HISTORY_FILE = KNOWLEDGE_DIR / "history.json"

APP_NAME = "Enterprise RAG Assistant AI Service"
APP_VERSION = "0.1.0"

CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
TOP_K = 4

SUPPORTED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}

GLM_API_KEY = os.getenv("GLM_API_KEY", "").strip()
GLM_EMBEDDING_URL = os.getenv(
    "GLM_EMBEDDING_URL",
    "https://open.bigmodel.cn/api/paas/v4/embeddings",
)
GLM_EMBEDDING_MODEL = os.getenv("GLM_EMBEDDING_MODEL", "embedding-3")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))
