import json
import math
import re
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from backend.ai_service.config import INDEX_FILE, KNOWLEDGE_DIR
from backend.ai_service.services.embedding_service import GLMEmbeddingClient


TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


@dataclass
class DocumentChunk:
    id: str
    document_id: str
    document_name: str
    chunk_index: int
    content: str
    metadata: dict
    created_at: str
    embedding: list[float] | None = None
    embedding_model: str | None = None


@dataclass
class SearchResult:
    chunk: DocumentChunk
    score: float


class LocalVectorStore:
    """Small persistent vector store with GLM dense embeddings and sparse fallback."""

    def __init__(
        self,
        index_file: Path = INDEX_FILE,
        embedding_client: GLMEmbeddingClient | None = None,
    ) -> None:
        self.index_file = index_file
        self.embedding_client = embedding_client or GLMEmbeddingClient()
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        self._chunks: list[DocumentChunk] = self._load()

    def add_document(
        self,
        document_name: str,
        chunks: Iterable[str],
        metadata: dict | None = None,
    ) -> tuple[str, int]:
        document_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        base_metadata = metadata or {}

        contents = [content for content in chunks if content.strip()]
        embeddings = self._embed_contents(contents)

        new_chunks = [
            DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                document_name=document_name,
                chunk_index=index,
                content=content,
                metadata=base_metadata,
                created_at=now,
                embedding=embeddings[index] if embeddings else None,
                embedding_model=self.embedding_client.model if embeddings else None,
            )
            for index, content in enumerate(contents)
        ]

        self._chunks.extend(new_chunks)
        self._save()
        return document_id, len(new_chunks)

    def list_documents(self) -> list[dict]:
        documents: dict[str, dict] = {}
        for chunk in self._chunks:
            entry = documents.setdefault(
                chunk.document_id,
                {
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "chunk_count": 0,
                    "created_at": chunk.created_at,
                    "metadata": chunk.metadata,
                },
            )
            entry["chunk_count"] += 1
        return sorted(documents.values(), key=lambda item: item["created_at"], reverse=True)

    def delete_document(self, document_id: str) -> int:
        before = len(self._chunks)
        self._chunks = [chunk for chunk in self._chunks if chunk.document_id != document_id]
        deleted = before - len(self._chunks)
        if deleted:
            self._save()
        return deleted

    def clear(self) -> None:
        self._chunks = []
        self._save()

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        if self.embedding_client.enabled and self._has_dense_embeddings():
            return self._dense_search(query, top_k=top_k)
        return self._sparse_search(query, top_k=top_k)

    def _dense_search(self, query: str, top_k: int) -> list[SearchResult]:
        query_embedding = self.embedding_client.embed_texts([query])[0]
        results: list[SearchResult] = []
        for chunk in self._chunks:
            if not chunk.embedding:
                continue
            score = _dense_cosine_similarity(query_embedding, chunk.embedding)
            if score > 0:
                results.append(SearchResult(chunk=chunk, score=score))

        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def _sparse_search(self, query: str, top_k: int) -> list[SearchResult]:
        query_vector = _to_vector(query)
        if not query_vector:
            return []

        results: list[SearchResult] = []
        for chunk in self._chunks:
            score = _cosine_similarity(query_vector, _to_vector(chunk.content))
            if score > 0:
                results.append(SearchResult(chunk=chunk, score=score))

        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def _embed_contents(self, contents: list[str]) -> list[list[float]]:
        if not self.embedding_client.enabled or not contents:
            return []
        return self.embedding_client.embed_texts(contents)

    def _has_dense_embeddings(self) -> bool:
        return any(chunk.embedding for chunk in self._chunks)

    def _load(self) -> list[DocumentChunk]:
        if not self.index_file.exists():
            return []
        payload = json.loads(self.index_file.read_text(encoding="utf-8"))
        return [DocumentChunk(**item) for item in payload]

    def _save(self) -> None:
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(chunk) for chunk in self._chunks]
        self.index_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _tokenize(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        if _contains_cjk(token) and len(token) > 1:
            expanded.extend(token[index : index + 2] for index in range(len(token) - 1))
    return expanded


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _to_vector(text: str) -> Counter:
    return Counter(_tokenize(text))


def _cosine_similarity(left: Counter, right: Counter) -> float:
    shared = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _dense_cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)
