import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.ai_service.agent.planner import PlannerService
from backend.ai_service.application.orchestrator import OrchestratorService
from backend.ai_service.application.rag_facade import RAGService
from backend.ai_service.llm.chat_client import ChatModelDelta, ChatModelResponse
from backend.ai_service.retrieval.embeddings import BailianEmbeddingClient
from backend.ai_service.retrieval.vector_store import LocalVectorStore
from backend.ai_service.storage.history import HistoryService


def test_rag_answer_mode_uses_selected_chat_model() -> None:
    class FakeChatClient:
        enabled = True

        def complete(self, messages, mode, temperature=0.2, tools=None, tool_choice=None):
            assert mode == "thinking"
            assert "When are reimbursements paid?" in messages[-1]["content"]
            if "路由分类器" in messages[0]["content"]:
                return ChatModelResponse(
                    content='{"needs_knowledge":true,"reason":"Policy question."}',
                    reasoning_content="",
                    model="qwen3.5-flash",
                )
            return ChatModelResponse(
                content="Reimbursements are paid within three business days after approval. [1]",
                reasoning_content="",
                model="qwen3.5-flash",
            )

    with TemporaryDirectory() as directory:
        vector_store = LocalVectorStore(
            index_file=Path(directory) / "chunks.json",
            embedding_client=BailianEmbeddingClient(api_key=""),
        )
        vector_store.add_document(
            document_name="policy.txt",
            chunks=["Reimbursements are paid within three business days after finance approval."],
        )
        service = RAGService(
            vector_store=vector_store,
            history_service=HistoryService(history_file=Path(directory) / "history.json"),
            chat_client=FakeChatClient(),
        )

        payload = service.ask("When are reimbursements paid?", answer_mode="thinking")

    assert payload["answer_mode"] == "thinking"
    assert payload["model"] == "qwen3.5-flash"
    assert "three business days" in payload["answer"]
    assert payload["trace_id"]
    assert any(step["step"] == "agent.answer" for step in payload["route"])


def test_rag_ignores_dense_results_below_score_threshold() -> None:
    class FakeEmbeddingClient:
        enabled = True
        model = "fake-embedding"

        def embed_texts(self, texts):
            embeddings = []
            for text in texts:
                if "reimbursement" in text.lower():
                    embeddings.append([1.0, 0.0])
                else:
                    embeddings.append([0.0, 1.0])
            return embeddings

    class PlannerChatClient:
        """Returns Route B so the executor searches and gets empty results."""

        enabled = True

        def complete(self, messages, mode, temperature=0.2, tools=None, tool_choice=None):
            return ChatModelResponse(
                content='{"needs_knowledge":true,"reason":"Check KB."}',
                reasoning_content="",
                model="fake-planner",
            )

    class UnexpectedChatClient:
        enabled = True

        def complete(self, messages, mode, temperature=0.2, tools=None, tool_choice=None):
            raise AssertionError("chat model should not be called for irrelevant retrieval")

    with TemporaryDirectory() as directory:
        vector_store = LocalVectorStore(
            index_file=Path(directory) / "chunks.json",
            embedding_client=FakeEmbeddingClient(),
            score_threshold=0.45,
        )
        vector_store.add_document(
            document_name="policy.txt",
            chunks=["Reimbursement requests are paid after finance approval."],
        )
        orchestrator = OrchestratorService(
            vector_store=vector_store,
            history_service=HistoryService(history_file=Path(directory) / "history.json"),
            planner=PlannerService(chat_client=PlannerChatClient()),
            chat_client=UnexpectedChatClient(),
        )
        service = RAGService(orchestrator=orchestrator)

        payload = service.ask("How should the data center firewall be configured?")

    assert payload["sources"] == []
    assert payload["model"] is None


def test_rag_agent_runs_react_tool_loop() -> None:
    class FakeReActChatClient:
        enabled = True

        def __init__(self) -> None:
            self.calls = 0
            self.tool_call_requested = False

        def complete(self, messages, mode, temperature=0.2, tools=None, tool_choice=None):
            self.calls += 1
            if "路由分类器" in messages[0]["content"]:
                return ChatModelResponse(
                    content='{"needs_knowledge":true,"reason":"Enterprise policy question."}',
                    reasoning_content="",
                    model="fake-react-model",
                )

            if tools and not self.tool_call_requested:
                assert tools
                self.tool_call_requested = True
                return ChatModelResponse(
                    content="",
                    reasoning_content="",
                    model="fake-react-model",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "knowledge_search",
                                "arguments": '{"query":"reimbursement approval payment"}',
                            },
                        }
                    ],
                )

            if "standalone_query" in messages[-1]["content"]:
                return ChatModelResponse(
                    content='{"standalone_query":"When are reimbursements paid?","semantic_queries":["When are reimbursements paid?"]}',
                    reasoning_content="",
                    model="fake-react-model",
                )

            assert "Reimbursement requests are paid" in messages[-1]["content"]
            return ChatModelResponse(
                content="Finance pays reimbursement requests after approval. [1]",
                reasoning_content="",
                model="fake-react-model",
            )

    with TemporaryDirectory() as directory:
        vector_store = LocalVectorStore(
            index_file=Path(directory) / "chunks.json",
            embedding_client=BailianEmbeddingClient(api_key=""),
        )
        vector_store.add_document(
            document_name="policy.txt",
            chunks=["Reimbursement requests are paid after finance approval."],
        )
        chat_client = FakeReActChatClient()
        service = RAGService(
            vector_store=vector_store,
            history_service=HistoryService(history_file=Path(directory) / "history.json"),
            chat_client=chat_client,
        )

        payload = service.ask("When are reimbursements paid?")

    assert chat_client.calls >= 4
    assert chat_client.tool_call_requested
    assert payload["answer"] == "Finance pays reimbursement requests after approval. [1]"
    assert payload["sources"]
    assert any(step["action"] == "knowledge_search" for step in payload["agent_steps"])
    assert any(step["step"] == "memory.append_turn" for step in payload["route"])


def test_follow_up_question_includes_loaded_conversation_memory() -> None:
    class MemoryAwareChatClient:
        enabled = True

        def __init__(self) -> None:
            self.agent_calls = 0

        def complete(self, messages, mode, temperature=0.2, tools=None, tool_choice=None):
            if "路由分类器" in messages[0]["content"]:
                return ChatModelResponse(
                    content='{"needs_knowledge":false,"reason":"Follow-up can use memory."}',
                    reasoning_content="",
                    model="fake-planner",
                )

            self.agent_calls += 1
            prompt = messages[-1]["content"]
            if self.agent_calls == 1:
                return ChatModelResponse(
                    content="Alpha answer from the first turn.",
                    reasoning_content="",
                    model="fake-agent",
                )

            assert "Alpha answer from the first turn." in prompt
            assert "What was my previous answer?" in prompt
            return ChatModelResponse(
                content="Your previous answer was Alpha answer from the first turn.",
                reasoning_content="",
                model="fake-agent",
            )

    with TemporaryDirectory() as directory:
        vector_store = LocalVectorStore(
            index_file=Path(directory) / "chunks.json",
            embedding_client=BailianEmbeddingClient(api_key=""),
        )
        chat_client = MemoryAwareChatClient()
        orchestrator = OrchestratorService(
            vector_store=vector_store,
            history_service=HistoryService(history_file=Path(directory) / "history.json"),
            chat_client=chat_client,
        )

        first = orchestrator.handle_chat(
            question="What was my previous answer?",
            user_id="user-1",
            tenant_id="tenant-1",
        )
        second = orchestrator.handle_chat(
            question="Repeat it.",
            conversation_id=first["conversation_id"],
            user_id="user-1",
            tenant_id="tenant-1",
        )

    assert second["conversation_id"] == first["conversation_id"]
    assert "Alpha answer" in second["answer"]
    assert chat_client.agent_calls == 2


def test_rag_stream_ask_emits_deltas_and_done() -> None:
    class FakeStreamingChatClient:
        enabled = True

        def complete(self, messages, mode, temperature=0.2, tools=None, tool_choice=None):
            if "路由分类器" in messages[0]["content"]:
                return ChatModelResponse(
                    content='{"needs_knowledge":true,"reason":"Policy question."}',
                    reasoning_content="",
                    model="qwen3.7-plus",
                )
            if "企业知识库 RAG 助手" in messages[0]["content"]:
                return ChatModelResponse(
                    content="Reimbursements are paid within three business days after finance approval. [1]",
                    reasoning_content="",
                    model="qwen3.7-plus",
                )
            raise AssertionError("Unexpected complete call for streaming test")

        async def stream_complete(self, messages, mode, temperature=0.2):
            assert mode == "fast"
            yield ChatModelDelta(content="Three ", model="qwen3.7-plus")
            yield ChatModelDelta(content="business days. [1]", model="qwen3.7-plus")

    async def collect_events(service: RAGService) -> list[dict]:
        return [
            event
            async for event in service.stream_ask(
                "When are reimbursements paid?",
                answer_mode="fast",
            )
        ]

    with TemporaryDirectory() as directory:
        vector_store = LocalVectorStore(
            index_file=Path(directory) / "chunks.json",
            embedding_client=BailianEmbeddingClient(api_key=""),
        )
        vector_store.add_document(
            document_name="policy.txt",
            chunks=["Reimbursements are paid within three business days after finance approval."],
        )
        service = RAGService(
            vector_store=vector_store,
            history_service=HistoryService(history_file=Path(directory) / "history.json"),
            chat_client=FakeStreamingChatClient(),
        )

        events = asyncio.run(collect_events(service))

    types = [event["type"] for event in events]
    assert types[0] == "phase"
    assert "plan" in types
    assert "route_step" in types
    assert types.count("answer_delta") >= 2
    assert events[-2]["type"] == "sources"
    assert events[-1]["type"] == "done"
    assert events[-1]["model"] == "qwen3.7-plus"
    assert events[-1]["trace_id"]
    assert any(step["step"] == "tool.knowledge_search" for step in events[-1]["route"])
    plan_event = next(event for event in events if event["type"] == "plan")
    assert plan_event["steps"]
    assert any(event["layer"] == "planner" for event in events if event["type"] == "phase")
