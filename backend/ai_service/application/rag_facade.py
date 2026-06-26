from collections.abc import AsyncIterator

from backend.ai_service.llm.chat_client import AnswerMode, BailianChatClient
from backend.ai_service.storage.history import HistoryService
from backend.ai_service.application.orchestrator import OrchestratorService


class RAGService:
    """Compatibility facade for the layered orchestrator pipeline."""

    def __init__(
        self,
        vector_store=None,
        history_service: HistoryService | None = None,
        chat_client: BailianChatClient | None = None,
        orchestrator: OrchestratorService | None = None,
    ) -> None:
        self.orchestrator = orchestrator or OrchestratorService(
            vector_store=vector_store,
            history_service=history_service,
            chat_client=chat_client,
        )

    def ask(
        self,
        question: str,
        conversation_id: str | None = None,
        top_k: int | None = None,
        answer_mode: AnswerMode = "fast",
    ) -> dict:
        return self.orchestrator.handle_chat(
            question=question,
            conversation_id=conversation_id,
            top_k=top_k,
            answer_mode=answer_mode,
        )

    async def stream_ask(
        self,
        question: str,
        conversation_id: str | None = None,
        top_k: int | None = None,
        answer_mode: AnswerMode = "fast",
    ) -> AsyncIterator[dict]:
        async for event in self.orchestrator.stream_chat(
            question=question,
            conversation_id=conversation_id,
            top_k=top_k,
            answer_mode=answer_mode,
        ):
            yield event
