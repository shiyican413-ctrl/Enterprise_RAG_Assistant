from backend.ai_service.config import TOP_K
from backend.ai_service.services.history_service import HistoryService
from backend.ai_service.services.vector_store_service import LocalVectorStore, SearchResult


class RAGService:
    def __init__(
        self,
        vector_store: LocalVectorStore | None = None,
        history_service: HistoryService | None = None,
    ) -> None:
        self.vector_store = vector_store or LocalVectorStore()
        self.history_service = history_service or HistoryService()

    def ask(
        self,
        question: str,
        conversation_id: str | None = None,
        top_k: int = TOP_K,
    ) -> dict:
        results = self.vector_store.search(question, top_k=top_k)
        sources = [_source_payload(result) for result in results]
        answer = _build_answer(question, results)
        turn = self.history_service.append_turn(
            question=question,
            answer=answer,
            sources=sources,
            conversation_id=conversation_id,
        )

        return {
            "conversation_id": turn["conversation_id"],
            "answer": answer,
            "sources": sources,
        }


def _build_answer(question: str, results: list[SearchResult]) -> str:
    if not results:
        return (
            "我还没有在当前知识库中检索到足够相关的内容。"
            "建议先上传企业制度、产品手册或 FAQ 文档后再提问。"
        )

    evidence = "\n".join(
        f"{index}. {result.chunk.content[:260]}"
        for index, result in enumerate(results[:3], start=1)
    )
    return (
        f"根据当前知识库中最相关的资料，关于“{question}”可以这样理解：\n\n"
        f"{evidence}\n\n"
        "以上回答来自检索片段的归纳整理。第一版先使用本地检索和模板生成，"
        "后续可把这里替换为通义千问、Ollama 或 OpenAI Compatible API 生成。"
    )


def _source_payload(result: SearchResult) -> dict:
    chunk = result.chunk
    return {
        "document_id": chunk.document_id,
        "document_name": chunk.document_name,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "snippet": chunk.content[:360],
        "score": round(result.score, 4),
        "metadata": chunk.metadata,
    }
