import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        if any("\u4e00" <= char <= "\u9fff" for char in token) and len(token) > 1:
            expanded.extend(token[index : index + 2] for index in range(len(token) - 1))
    return expanded


@dataclass(frozen=True)
class WeightedCandidate:
    result: Any
    dense_score: float = 0.0
    sparse_score: float = 0.0


class BM25Scorer:
    def __init__(self, documents: Iterable[tuple[str, str]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.documents: dict[str, list[str]] = {
            doc_id: _tokenize(text) for doc_id, text in documents
        }
        self.doc_count = len(self.documents)
        lengths = [len(tokens) for tokens in self.documents.values()]
        self.avg_doc_len = sum(lengths) / len(lengths) if lengths else 0.0
        self.document_frequency: Counter[str] = Counter()
        for tokens in self.documents.values():
            self.document_frequency.update(set(tokens))

    def score(self, query: str, document_id: str) -> float:
        query_terms = _tokenize(query)
        document_terms = self.documents.get(document_id) or []
        if not query_terms or not document_terms or not self.avg_doc_len:
            return 0.0

        term_counts = Counter(document_terms)
        score = 0.0
        doc_len = len(document_terms)
        for term in query_terms:
            frequency = term_counts.get(term, 0)
            if not frequency:
                continue
            df = self.document_frequency.get(term, 0)
            idf = math.log(1 + (self.doc_count - df + 0.5) / (df + 0.5))
            denominator = frequency + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
            score += idf * (frequency * (self.k1 + 1)) / denominator
        return score


def fuse_results(
    dense_results: list[Any],
    sparse_results: list[Any],
    *,
    top_k: int,
    dense_weight: float = 0.62,
    sparse_weight: float = 0.38,
) -> list[Any]:
    from backend.ai_service.retrieval.vector_store import SearchResult

    candidates: dict[str, WeightedCandidate] = {}
    max_dense = max((result.score for result in dense_results), default=0.0)
    max_sparse = max((result.score for result in sparse_results), default=0.0)

    for result in dense_results:
        normalized = result.score / max_dense if max_dense else result.score
        existing = candidates.get(result.chunk.id)
        sparse_score = existing.sparse_score if existing else 0.0
        candidates[result.chunk.id] = WeightedCandidate(
            result=result,
            dense_score=max(normalized, existing.dense_score if existing else 0.0),
            sparse_score=sparse_score,
        )

    for result in sparse_results:
        normalized = result.score / max_sparse if max_sparse else result.score
        existing = candidates.get(result.chunk.id)
        candidates[result.chunk.id] = WeightedCandidate(
            result=existing.result if existing else result,
            dense_score=existing.dense_score if existing else 0.0,
            sparse_score=max(normalized, existing.sparse_score if existing else 0.0),
        )

    fused = [
        SearchResult(
            chunk=candidate.result.chunk,
            score=dense_weight * candidate.dense_score + sparse_weight * candidate.sparse_score,
        )
        for candidate in candidates.values()
    ]
    fused.sort(key=lambda item: (-item.score, item.chunk.id))
    return fused[:top_k]
