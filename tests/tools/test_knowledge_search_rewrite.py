from backend.ai_service.retrieval.vector_store import DocumentChunk, SearchResult
from backend.ai_service.tools.base import ToolContext
from backend.ai_service.tools.knowledge_search_tool import KnowledgeSearchTool


def _chunk(chunk_id: str, name: str = "policy.md") -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        document_id=f"doc-{chunk_id}",
        document_name=name,
        chunk_index=0,
        content="费用报销审批通过后由财务打款。",
        metadata={},
        created_at="2026-01-01T00:00:00Z",
    )


class _RecordingVectorStore:
    def __init__(self):
        self.queries = []
        self.shared = _chunk("shared")
        self.single = _chunk("single")

    def search(self, query, top_k):
        self.queries.append((query, top_k))
        if len(self.queries) == 1:
            return [SearchResult(self.shared, 0.8), SearchResult(self.single, 0.9)]
        return [SearchResult(self.shared, 0.8)]


def test_searches_multiple_queries_deduplicates_and_returns_trace_metadata():
    store = _RecordingVectorStore()
    result = KnowledgeSearchTool(store).run(
        {"query": "报销多久到账"},
        ToolContext(trace_id="trace-1", top_k=3),
    )

    assert len(store.queries) >= 3
    assert len(result.raw_results) == 2
    assert result.raw_results[0].chunk.id == "shared"
    assert len(result.sources[0]["matched_queries"]) >= 2
    assert result.sources[0]["fused_score"] > 0.8
    metadata = result.metadata["query_rewrite"]
    assert metadata["original_query"] == "报销多久到账"
    assert metadata["retrieved_queries"] == len(store.queries)


def test_empty_query_does_not_call_vector_store():
    store = _RecordingVectorStore()
    result = KnowledgeSearchTool(store).run(
        {"query": "  "},
        ToolContext(trace_id="trace-1", top_k=3),
    )

    assert store.queries == []
    assert result.raw_results == []
    assert result.metadata["query_rewrite"]["needs_clarification"] is True
