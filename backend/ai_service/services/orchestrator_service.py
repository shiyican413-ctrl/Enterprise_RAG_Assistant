from collections.abc import AsyncIterator

from backend.ai_service.config import TOP_K
from backend.ai_service.services.chat_model_service import AnswerMode, DoubaoChatClient
from backend.ai_service.services.executor_service import ExecutorService
from backend.ai_service.services.guardrail_service import GuardrailService
from backend.ai_service.services.history_service import HistoryService, PostgresHistoryService
from backend.ai_service.services.memory_service import MemoryService
from backend.ai_service.services.planner_service import PlannerService
from backend.ai_service.services.trace_service import TraceService
from backend.ai_service.services.vector_store_service import PostgresVectorStore
from backend.ai_service.services.workflow_service import ChatWorkflow
from backend.ai_service.tools.knowledge_search_tool import KnowledgeSearchTool
from backend.ai_service.tools.registry import ToolRegistry


class OrchestratorService:
    def __init__(
        self,
        *,
        vector_store: PostgresVectorStore | None = None,
        history_service: HistoryService | None = None,
        chat_client: DoubaoChatClient | None = None,
        planner: PlannerService | None = None,
        executor: ExecutorService | None = None,
        memory: MemoryService | None = None,
        trace_service: TraceService | None = None,
        tool_registry: ToolRegistry | None = None,
        workflow: ChatWorkflow | None = None,
        guardrails: GuardrailService | None = None,
    ) -> None:
        self.vector_store = vector_store or PostgresVectorStore()
        self.history_service = history_service or PostgresHistoryService()
        self.chat_client = chat_client or DoubaoChatClient()
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
    ) -> dict:
        trace = self.trace_service.start_trace()
        return self.workflow.run_chat(
            trace=trace,
            question=question,
            conversation_id=conversation_id,
            top_k=top_k,
            answer_mode=answer_mode,
        )

    async def stream_chat(
        self,
        *,
        question: str,
        conversation_id: str | None = None,
        top_k: int = TOP_K,
        answer_mode: AnswerMode = "fast",
    ) -> AsyncIterator[dict]:
        trace = self.trace_service.start_trace()
        async for event in self.workflow.stream_chat(
            trace=trace,
            question=question,
            conversation_id=conversation_id,
            top_k=top_k,
            answer_mode=answer_mode,
        ):
            yield event
