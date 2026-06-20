from backend.ai_service.retrieval.vector_store import SearchResult
from backend.ai_service.tools.base import ToolContext, ToolResult


class KnowledgeSearchTool:
    name = "knowledge_search"
    description = (
        "检索企业知识库。输入 JSON："
        '{"query":"用户问题或聚焦后的检索词"}。'
    )

    def __init__(self, vector_store) -> None:
        self.vector_store = vector_store

    def run(self, payload: dict, context: ToolContext) -> ToolResult:
        query = str(payload.get("query") or "").strip()
        results = self.vector_store.search(query, top_k=context.top_k) if query else []
        sources = [_source_payload(result) for result in results]

        if not results:
            return ToolResult(
                content="未检索到相关知识库片段。",
                sources=[],
                raw_results=[],
            )

        evidence = "\n".join(
            (
                f"[{index}] {result.chunk.document_name} "
                f"片段 {result.chunk.chunk_index}: {result.chunk.content[:500]}"
            )
            for index, result in enumerate(results, start=1)
        )
        return ToolResult(content=evidence, sources=sources, raw_results=results)


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
