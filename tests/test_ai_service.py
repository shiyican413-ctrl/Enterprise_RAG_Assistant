import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.ai_service.main import app
from backend.ai_service.services.chat_model_service import ChatModelDelta, ChatModelResponse
from backend.ai_service.services.embedding_service import GLMEmbeddingClient
from backend.ai_service.services.history_service import HistoryService
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
        json={"question": "报销多久可以打款？"},
    )
    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert payload["answer"]
    assert payload["sources"]


def test_rag_answer_mode_uses_selected_chat_model() -> None:
    class FakeChatClient:
        enabled = True

        def complete(self, messages, mode, temperature=0.2):
            assert mode == "thinking"
            assert "用户问题：报销多久可以打款？" in messages[-1]["content"]
            return ChatModelResponse(
                content="审批通过后三个工作日内打款。[1]",
                reasoning_content="",
                model="GLM-4.1V-Thinking-Flash",
            )

    with TemporaryDirectory() as directory:
        vector_store = LocalVectorStore(
            index_file=Path(directory) / "chunks.json",
            embedding_client=GLMEmbeddingClient(api_key=""),
        )
        vector_store.add_document(
            document_name="policy.txt",
            chunks=["报销审批通过后，一般会在三个工作日内完成打款。"],
        )
        service = RAGService(
            vector_store=vector_store,
            history_service=HistoryService(history_file=Path(directory) / "history.json"),
            chat_client=FakeChatClient(),
        )

        payload = service.ask("报销多久可以打款？", answer_mode="thinking")

    assert payload["answer_mode"] == "thinking"
    assert payload["model"] == "GLM-4.1V-Thinking-Flash"
    assert "三个工作日" in payload["answer"]


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


def test_rag_stream_ask_emits_deltas_and_done() -> None:
    class FakeStreamingChatClient:
        enabled = True

        async def stream_complete(self, messages, mode, temperature=0.2):
            assert mode == "fast"
            yield ChatModelDelta(content="三个", model="GLM-4V-Flash")
            yield ChatModelDelta(content="工作日内打款。[1]", model="GLM-4V-Flash")

    async def collect_events(service: RAGService) -> list[dict]:
        return [
            event
            async for event in service.stream_ask(
                "报销多久可以打款？",
                answer_mode="fast",
            )
        ]

    with TemporaryDirectory() as directory:
        vector_store = LocalVectorStore(
            index_file=Path(directory) / "chunks.json",
            embedding_client=GLMEmbeddingClient(api_key=""),
        )
        vector_store.add_document(
            document_name="policy.txt",
            chunks=["报销审批通过后，一般会在三个工作日内完成打款。"],
        )
        service = RAGService(
            vector_store=vector_store,
            history_service=HistoryService(history_file=Path(directory) / "history.json"),
            chat_client=FakeStreamingChatClient(),
        )

        events = asyncio.run(collect_events(service))

    assert [event["type"] for event in events[:2]] == ["answer_delta", "answer_delta"]
    assert events[-2]["type"] == "sources"
    assert events[-1]["type"] == "done"
    assert events[-1]["model"] == "GLM-4V-Flash"
