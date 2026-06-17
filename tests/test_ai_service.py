import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.ai_service.main import app
from backend.ai_service.services.chat_model_service import ChatModelDelta, ChatModelResponse
from backend.ai_service.services.embedding_service import BailianEmbeddingClient
from backend.ai_service.services.history_service import HistoryService
from backend.ai_service.services.planner_service import PlannerService
from backend.ai_service.services.rag_service import RAGService
from backend.ai_service.services.vector_store_service import LocalVectorStore


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_and_ask() -> None:
    sample = Path("data/sample_policy.txt")
    with sample.open("rb") as file:
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("sample_policy.txt", file, "text/plain")},
        )
    assert upload_response.status_code == 200
    assert upload_response.json()["chunk_count"] > 0

    ask_response = client.post(
        "/api/chat/ask",
        json={"question": "When are reimbursements paid?"},
    )
    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert payload["answer"]
    assert payload["sources"]
    assert payload["trace_id"]
    assert [step["step"] for step in payload["route"]][:3] == [
        "guardrails.input",
        "memory.load",
        "planner.create_plan",
    ]


def test_rag_answer_mode_uses_selected_chat_model() -> None:
    class FakeChatClient:
        enabled = True

        def complete(self, messages, mode, temperature=0.2):
            assert mode == "thinking"
            assert "When are reimbursements paid?" in messages[-1]["content"]
            return ChatModelResponse(
                content="Reimbursements are paid within three business days after approval. [1]",
                reasoning_content="",
                model="doubao-seed-2-0-lite-260428",
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
    assert payload["model"] == "doubao-seed-2-0-lite-260428"
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

    class UnexpectedChatClient:
        enabled = True

        def complete(self, messages, mode, temperature=0.2):
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
        service = RAGService(
            vector_store=vector_store,
            history_service=HistoryService(history_file=Path(directory) / "history.json"),
            chat_client=UnexpectedChatClient(),
        )

        payload = service.ask("How should the data center firewall be configured?")

    assert payload["sources"] == []
    assert payload["model"] is None


def test_planner_uses_llm_for_complex_tasks() -> None:
    class FakePlannerChatClient:
        enabled = True

        def complete(self, messages, mode, temperature=0.2):
            assert mode == "thinking"
            assert "Allowed step types" in messages[0]["content"]
            return ChatModelResponse(
                content=(
                    '{"rationale":"Complex comparison needs evidence first.",'
                    '"steps":['
                    '{"name":"tool.knowledge_search","step_type":"knowledge_search","input":{}},'
                    '{"name":"model.answer","step_type":"answer_generation","input":{}}'
                    ']}'
                ),
                reasoning_content="",
                model="fake-planner",
            )

    planner = PlannerService(chat_client=FakePlannerChatClient())
    plan = planner.create_plan(
        question="Compare the reimbursement policy and travel policy, then summarize the differences.",
        answer_mode="thinking",
        memory=[],
    )

    assert plan.strategy == "llm"
    assert [step.step_type for step in plan.steps] == [
        "knowledge_search",
        "answer_generation",
    ]


def test_rag_agent_runs_react_tool_loop() -> None:
    class FakeReActChatClient:
        enabled = True

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, mode, temperature=0.2):
            self.calls += 1
            if self.calls == 1:
                return ChatModelResponse(
                    content=(
                        '{"type":"action","thought":"Need private policy evidence.",'
                        '"action":"knowledge_search",'
                        '"action_input":{"query":"reimbursement approval payment"}}'
                    ),
                    reasoning_content="",
                    model="fake-react-model",
                )

            assert "Reimbursement requests are paid" in messages[-1]["content"]
            return ChatModelResponse(
                content=(
                    '{"type":"final","thought":"Evidence found.",'
                    '"answer":"Finance pays reimbursement requests after approval. [1]"}'
                ),
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

    assert chat_client.calls == 2
    assert payload["answer"] == "Finance pays reimbursement requests after approval. [1]"
    assert payload["sources"]
    assert payload["agent_steps"][0]["action"] == "knowledge_search"
    assert any(step["step"] == "memory.append_turn" for step in payload["route"])


def test_rag_stream_ask_emits_deltas_and_done() -> None:
    class FakeStreamingChatClient:
        enabled = True

        async def stream_complete(self, messages, mode, temperature=0.2):
            assert mode == "fast"
            yield ChatModelDelta(content="Three ", model="doubao-seed-2-0-lite-260428")
            yield ChatModelDelta(content="business days. [1]", model="doubao-seed-2-0-lite-260428")

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
    # Layered live protocol: phase / plan / route_step events now precede the
    # streamed answer, so the user sees each layer working in real time.
    assert types[0] == "phase"
    assert "plan" in types
    assert "route_step" in types
    assert types.count("answer_delta") >= 2
    assert events[-2]["type"] == "sources"
    assert events[-1]["type"] == "done"
    assert events[-1]["model"] == "doubao-seed-2-0-lite-260428"
    assert events[-1]["trace_id"]
    assert any(step["step"] == "tool.knowledge_search" for step in events[-1]["route"])
    # The planner's plan is surfaced live before the answer streams.
    plan_event = next(event for event in events if event["type"] == "plan")
    assert plan_event["steps"]
    assert any(event["layer"] == "planner" for event in events if event["type"] == "phase")

