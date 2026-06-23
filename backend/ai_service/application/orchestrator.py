from collections.abc import AsyncIterator

from backend.ai_service.core.config import TOP_K
from backend.ai_service.llm.chat_client import AnswerMode, BailianChatClient
from backend.ai_service.agent.executor import ExecutorService
from backend.ai_service.agent.guardrails import GuardrailService
from backend.ai_service.storage.history import HistoryService, PostgresHistoryService
from backend.ai_service.application.memory import MemoryService
from backend.ai_service.agent.planner import PlannerService
from backend.ai_service.storage.factory import create_vector_store
from backend.ai_service.observability.tracing import TraceService
from backend.ai_service.application.chat_workflow import ChatWorkflow
from backend.ai_service.tools.knowledge_search_tool import KnowledgeSearchTool
from backend.ai_service.tools.registry import ToolRegistry


class OrchestratorService:
    def __init__(
        self,
        *,
        vector_store=None,
        history_service: HistoryService | None = None,
        chat_client: BailianChatClient | None = None,
        planner: PlannerService | None = None,
        executor: ExecutorService | None = None,
        memory: MemoryService | None = None,
        trace_service: TraceService | None = None,
        tool_registry: ToolRegistry | None = None,
        workflow: ChatWorkflow | None = None,
        guardrails: GuardrailService | None = None,
    ) -> None:
        self.vector_store = vector_store or create_vector_store()
        self.history_service = history_service or PostgresHistoryService()
        self.chat_client = chat_client or BailianChatClient()
        self.trace_service = trace_service or TraceService()
        self.memory = memory or MemoryService(history_service=self.history_service)
        self.planner = planner or PlannerService(chat_client=self.chat_client)
        self.tool_registry = tool_registry or ToolRegistry(
            [KnowledgeSearchTool(self.vector_store)]
        )
        self.executor = executor or ExecutorService(
            tool_registry=self.tool_registry,
            chat_client=self.chat_client,
            trace_service=self.trace_service,
        )
        self.guardrails = guardrails or GuardrailService()
        self.workflow = workflow or ChatWorkflow(
            memory=self.memory,
            planner=self.planner,
            executor=self.executor,
            trace_service=self.trace_service,
            guardrails=self.guardrails,
        )

    def handle_chat(
        self,
        *,
        question: str,
        conversation_id: str | None = None,
        top_k: int = TOP_K,
        answer_mode: AnswerMode = "fast",
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        trace = self.trace_service.start_trace()
        return self.workflow.run_chat(
            trace=trace,
            question=question,
            conversation_id=conversation_id,
            top_k=top_k,
            answer_mode=answer_mode,
            user_id=user_id,
            tenant_id=tenant_id,
        )

    async def stream_chat(
        self,
        *,
        question: str,
        conversation_id: str | None = None,
        top_k: int = TOP_K,
        answer_mode: AnswerMode = "fast",
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> AsyncIterator[dict]:
        trace = self.trace_service.start_trace()
        async for event in self.workflow.stream_chat(
            trace=trace,
            question=question,
            conversation_id=conversation_id,
            top_k=top_k,
            answer_mode=answer_mode,
            user_id=user_id,
            tenant_id=tenant_id,
        ):
            yield event
