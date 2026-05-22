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


@dataclass
class SearchResult:
    chunk: DocumentChunk
    score: float


class LocalVectorStore:
    """Small persistent sparse-vector store for first-day RAG development."""

    def __init__(self, index_file: Path = INDEX_FILE) -> None:
        self.index_file = index_file
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

        new_chunks = [
            DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                document_name=document_name,
                chunk_index=index,
                content=content,
                metadata=base_metadata,
                created_at=now,
            )
            for index, content in enumerate(chunks)
            if content.strip()
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
        query_vector = _to_vector(query)
        if not query_vector:
            return []

        results: list[SearchResult] = []
        for chunk in self._chunks:
            score = _cosine_similarity(query_vector, _to_vector(chunk.content))
            if score > 0:
                results.append(SearchResult(chunk=chunk, score=score))

        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

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
