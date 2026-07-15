from dataclasses import replace
from typing import Any

import httpx

from backend.ai_service.core.config import (
    BAILIAN_RERANK_MODEL,
    BAILIAN_RERANK_URL,
    CHAT_TIMEOUT_SECONDS,
    DASHSCOPE_API_KEY,
    RERANK_ENABLED,
)
from backend.ai_service.retrieval.hybrid import _tokenize


class Reranker:
    def rerank(self, query: str, results: list[Any], top_k: int) -> list[Any]:
        raise NotImplementedError


class HybridReranker(Reranker):
    def __init__(
        self,
        api_key: str = DASHSCOPE_API_KEY,
        url: str = BAILIAN_RERANK_URL,
        model: str = BAILIAN_RERANK_MODEL,
        timeout_seconds: float = CHAT_TIMEOUT_SECONDS,
        enabled: bool = RERANK_ENABLED,
    ) -> None:
        self.api_key = api_key
        self.url = url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled

    def rerank(self, query: str, results: list[Any], top_k: int) -> list[Any]:
        if not results:
            return []
        if self.enabled and self.api_key:
            try:
                reranked = self._remote_rerank(query, results, top_k)
                if reranked:
                    return reranked
            except Exception:
                pass
        return self._lexical_rerank(query, results, top_k)

    def _remote_rerank(self, query: str, results: list[Any], top_k: int) -> list[Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        documents = [result.chunk.content for result in results]
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": min(top_k, len(documents)),
            "return_documents": False,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
        body = response.json()
        items = body.get("results") or body.get("data") or []
        reranked: list[Any] = []
        for item in items:
            index = item.get("index")
            if index is None:
                continue
            score = float(item.get("relevance_score", item.get("score", 0.0)) or 0.0)
            if 0 <= int(index) < len(results):
                reranked.append(replace(results[int(index)], score=score))
        reranked.sort(key=lambda item: (-item.score, item.chunk.id))
        return reranked[:top_k]

    def _lexical_rerank(self, query: str, results: list[Any], top_k: int) -> list[Any]:
        query_terms = set(_tokenize(query))
        if not query_terms:
            return results[:top_k]
        reranked: list[Any] = []
        for result in results:
            content_terms = set(_tokenize(result.chunk.content))
            title_terms = set(_tokenize(" ".join(result.chunk.metadata.get("title_path") or [])))
            overlap = len(query_terms & content_terms)
            title_overlap = len(query_terms & title_terms)
            lexical_score = (overlap + 1.5 * title_overlap) / max(len(query_terms), 1)
            reranked.append(replace(result, score=0.72 * result.score + 0.28 * lexical_score))
        reranked.sort(key=lambda item: (-item.score, item.chunk.id))
        return reranked[:top_k]
