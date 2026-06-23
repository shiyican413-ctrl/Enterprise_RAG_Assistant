from backend.ai_service.storage.history import HistoryService, PostgresHistoryService


class MemoryService:
    def __init__(self, history_service: HistoryService | None = None) -> None:
        self.history_service = history_service or PostgresHistoryService()

    def load_context(
        self, conversation_id: str | None, user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict]:
        if not conversation_id:
            return []
        return self.history_service.get_conversation(
            conversation_id, user_id=user_id, tenant_id=tenant_id
        )

    def append_turn(
        self,
        *,
        question: str,
        answer: str,
        sources: list[dict],
        conversation_id: str | None,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        return self.history_service.append_turn(
            question=question,
            answer=answer,
            sources=sources,
            conversation_id=conversation_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )
