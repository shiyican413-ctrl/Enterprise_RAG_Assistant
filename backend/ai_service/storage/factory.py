from backend.ai_service.core.config import (
    DATABASE_URL,
    MILVUS_COLLECTION,
    MILVUS_DB_NAME,
    MILVUS_TOKEN,
    MILVUS_URI,
    VECTOR_STORE_BACKEND,
)
from backend.ai_service.storage.history import HistoryService, PostgresHistoryService
from backend.ai_service.retrieval.vector_store import (
    LocalVectorStore,
    MilvusVectorStore,
)


def create_vector_store():
    if VECTOR_STORE_BACKEND == "milvus":
        return MilvusVectorStore(
            uri=MILVUS_URI,
            token=MILVUS_TOKEN,
            db_name=MILVUS_DB_NAME,
            collection_name=MILVUS_COLLECTION,
        )
    if VECTOR_STORE_BACKEND == "local":
        return LocalVectorStore()
    raise RuntimeError(
        "VECTOR_STORE_BACKEND must be one of: milvus, local"
    )


def create_history_service() -> HistoryService | PostgresHistoryService:
    if DATABASE_URL:
        return PostgresHistoryService(database_url=DATABASE_URL)
    return HistoryService()
