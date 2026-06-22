from dataclasses import dataclass, field

from backend.ai_service.retrieval.query_rewriter import QueryRewriteService
from backend.ai_service.retrieval.vector_store import SearchResult
from backend.ai_service.tools.base import ToolContext, ToolResult


RRF_K = 60


@dataclass
class _FusedCandidate:
    result: SearchResult
    vector_score: float
    rrf_score: float = 0.0
    matched_queries: list[str] = field(default_factory=list)


class KnowledgeSearchTool:
    name = "knowledge_search"
    description = (
        "检索企业知识库。输入 JSON："
        '{"query":"用户问题或聚焦后的检索词"}。'
    )

    def __init__(self, vector_store, query_rewriter=None) -> None:
        self.vector_store = vector_store
        self.query_rewriter = query_rewriter or QueryRewriteService()

    def run(self, payload: dict, context: ToolContext) -> ToolResult:
        query = str(payload.get("query") or "").strip()
        plan = self.query_rewriter.rewrite(query)
        results_by_query = [
            (semantic_query, self.vector_store.search(semantic_query, top_k=context.top_k))
            for semantic_query in plan.semantic_queries
        ]
        results, matched_queries = _fuse_results(results_by_query, top_k=context.top_k)
        sources = [
            _source_payload(result, matched_queries.get(result.chunk.id, []))
            for result in results
        ]
        rewrite_metadata = {
            **plan.to_dict(),
            "retrieved_queries": len(plan.semantic_queries),
        }

        if not results:
            return ToolResult(
                content="未检索到相关知识库片段。",
                sources=[],
                raw_results=[],
                metadata={"query_rewrite": rewrite_metadata},
            )

        evidence = "\n".join(
            (
                f"[{index}] {result.chunk.document_name} "
                f"片段 {result.chunk.chunk_index}: {result.chunk.content[:500]}"
            )
            for index, result in enumerate(results, start=1)
        )
        return ToolResult(
            content=evidence,
            sources=sources,
            raw_results=results,
            metadata={"query_rewrite": rewrite_metadata},
        )


def _source_payload(result: SearchResult, matched_queries: list[str]) -> dict:
    chunk = result.chunk
    return {
        "document_id": chunk.document_id,
        "document_name": chunk.document_name,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "snippet": chunk.content[:360],
        "score": round(result.score, 4),
        "fused_score": round(result.score, 4),
        "matched_query": matched_queries[0] if matched_queries else "",
        "matched_queries": matched_queries,
        "metadata": chunk.metadata,
    }


def _fuse_results(
    results_by_query: list[tuple[str, list[SearchResult]]],
    *,
    top_k: int,
) -> tuple[list[SearchResult], dict[str, list[str]]]:
    candidates: dict[str, _FusedCandidate] = {}
    for query, results in results_by_query:
        for rank, result in enumerate(results, start=1):
            chunk_id = result.chunk.id
            candidate = candidates.get(chunk_id)
            if candidate is None:
                candidate = _FusedCandidate(result=result, vector_score=result.score)
                candidates[chunk_id] = candidate
            elif result.score > candidate.vector_score:
                candidate.result = result
                candidate.vector_score = result.score
            candidate.rrf_score += 1 / (RRF_K + rank)
            if query not in candidate.matched_queries:
                candidate.matched_queries.append(query)

    if not candidates or top_k <= 0:
        return [], {}

    max_rrf = max(candidate.rrf_score for candidate in candidates.values()) or 1.0
    fused: list[tuple[SearchResult, list[str]]] = []
    for candidate in candidates.values():
        normalized_rrf = candidate.rrf_score / max_rrf
        score = 0.7 * candidate.vector_score + 0.3 * normalized_rrf
        fused.append(
            (
                SearchResult(chunk=candidate.result.chunk, score=score),
                candidate.matched_queries,
            )
        )

    fused.sort(key=lambda item: (-item[0].score, item[0].chunk.id))
    selected = fused[:top_k]
    return (
        [result for result, _ in selected],
        {result.chunk.id: queries for result, queries in selected},
    )
