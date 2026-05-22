from backend.ai_service.config import DATABASE_URL
from backend.ai_service.services.history_service import PostgresHistoryService
from backend.ai_service.services.vector_store_service import PostgresVectorStore


def create_vector_store() -> PostgresVectorStore:
    return PostgresVectorStore(database_url=DATABASE_URL)


def create_history_service() -> PostgresHistoryService:
    return PostgresHistoryService(database_url=DATABASE_URL)
