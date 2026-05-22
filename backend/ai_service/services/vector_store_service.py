import json
import math
import re
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from backend.ai_service.config import (
    DATABASE_URL,
    INDEX_FILE,
    KNOWLEDGE_DIR,
    VECTOR_SCORE_THRESHOLD,
)
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
        score_threshold: float = VECTOR_SCORE_THRESHOLD,
    ) -> None:
        self.index_file = index_file
        self.embedding_client = embedding_client or GLMEmbeddingClient()
        self.score_threshold = score_threshold
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

    def list_document_chunks(self, document_id: str) -> list[dict]:
        chunks = [
            chunk
            for chunk in self._chunks
            if chunk.document_id == document_id
        ]
        return [_chunk_payload(chunk) for chunk in sorted(chunks, key=lambda item: item.chunk_index)]

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
            if score >= self.score_threshold:
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


class PostgresVectorStore:
    """PostgreSQL + pgvector backed store with sparse-search fallback."""

    def __init__(
        self,
        database_url: str = DATABASE_URL,
        embedding_client: GLMEmbeddingClient | None = None,
        score_threshold: float = VECTOR_SCORE_THRESHOLD,
    ) -> None:
        if not database_url:
            raise RuntimeError("DATABASE_URL is required for PostgreSQL storage")
        self.database_url = database_url
        self.embedding_client = embedding_client or GLMEmbeddingClient()
        self.score_threshold = score_threshold
        self._ensure_schema()

    def add_document(
        self,
        document_name: str,
        chunks: Iterable[str],
        metadata: dict | None = None,
    ) -> tuple[str, int]:
        document_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        base_metadata = metadata or {}
        contents = [content for content in chunks if content.strip()]
        embeddings = self._embed_contents(contents)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (id, name, metadata, created_at)
                    VALUES (%s::uuid, %s, %s::jsonb, %s)
                    """,
                    (document_id, document_name, _json(base_metadata), now),
                )
                for index, content in enumerate(contents):
                    embedding = embeddings[index] if embeddings else None
                    cur.execute(
                        """
                        INSERT INTO document_chunks (
                            id, document_id, document_name, chunk_index, content, metadata,
                            created_at, embedding, embedding_model
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb,
                            %s, %s::vector, %s
                        )
                        """,
                        (
                            str(uuid.uuid4()),
                            document_id,
                            document_name,
                            index,
                            content,
                            _json(base_metadata),
                            now,
                            _vector_literal(embedding) if embedding else None,
                            self.embedding_client.model if embedding else None,
                        ),
                    )
            conn.commit()

        return document_id, len(contents)

    def list_documents(self) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.id::text AS document_id,
                        d.name AS document_name,
                        COUNT(c.id)::int AS chunk_count,
                        d.created_at,
                        d.metadata
                    FROM documents d
                    LEFT JOIN document_chunks c ON c.document_id = d.id
                    GROUP BY d.id
                    ORDER BY d.created_at DESC
                    """
                )
                rows = cur.fetchall()
        return [
            {
                "document_id": row[0],
                "document_name": row[1],
                "chunk_count": row[2],
                "created_at": row[3].isoformat(),
                "metadata": row[4] or {},
            }
            for row in rows
        ]

    def delete_document(self, document_id: str) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM document_chunks WHERE document_id = %s::uuid",
                    (document_id,),
                )
                deleted = int(cur.fetchone()[0])
                cur.execute("DELETE FROM documents WHERE id = %s::uuid", (document_id,))
            conn.commit()
        return deleted

    def list_document_chunks(self, document_id: str) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id::text, document_id::text, document_name, chunk_index,
                        content, metadata, created_at, embedding::text,
                        embedding_model
                    FROM document_chunks
                    WHERE document_id = %s::uuid
                    ORDER BY chunk_index ASC
                    """,
                    (document_id,),
                )
                chunks = [_chunk_from_row(row) for row in cur.fetchall()]
        return [_chunk_payload(chunk) for chunk in chunks]

    def clear(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE document_chunks, documents CASCADE")
            conn.commit()

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        return self._dense_search(query, top_k=top_k)

    def _dense_search(self, query: str, top_k: int) -> list[SearchResult]:
        query_embedding = self.embedding_client.embed_texts([query])[0]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id::text, document_id::text, document_name, chunk_index,
                        content, metadata, created_at, embedding::text,
                        embedding_model,
                        1 - (embedding <=> %s::vector) AS score
                    FROM document_chunks
                    WHERE embedding IS NOT NULL
                        AND 1 - (embedding <=> %s::vector) >= %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (
                        _vector_literal(query_embedding),
                        _vector_literal(query_embedding),
                        self.score_threshold,
                        _vector_literal(query_embedding),
                        top_k,
                    ),
                )
                rows = cur.fetchall()
        return [
            SearchResult(chunk=_chunk_from_row(row), score=float(row[9] or 0))
            for row in rows
        ]

    def _sparse_search(self, query: str, top_k: int) -> list[SearchResult]:
        query_vector = _to_vector(query)
        if not query_vector:
            return []

        results: list[SearchResult] = []
        for chunk in self._load_chunks():
            score = _cosine_similarity(query_vector, _to_vector(chunk.content))
            if score > 0:
                results.append(SearchResult(chunk=chunk, score=score))
        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def _load_chunks(self) -> list[DocumentChunk]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id::text, document_id::text, document_name, chunk_index,
                        content, metadata, created_at, embedding::text,
                        embedding_model
                    FROM document_chunks
                    ORDER BY created_at DESC, chunk_index ASC
                    """
                )
                return [_chunk_from_row(row) for row in cur.fetchall()]

    def _embed_contents(self, contents: list[str]) -> list[list[float]]:
        if not contents:
            return []
        if not self.embedding_client.enabled:
            raise RuntimeError("GLM_API_KEY is required for pgvector document ingestion")
        return self.embedding_client.embed_texts(contents)

    def _has_dense_embeddings(self) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT EXISTS (SELECT 1 FROM document_chunks WHERE embedding IS NOT NULL)")
                return bool(cur.fetchone()[0])

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        id uuid PRIMARY KEY,
                        name text NOT NULL,
                        metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                        created_at timestamptz NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id uuid PRIMARY KEY,
                        document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        document_name text NOT NULL,
                        chunk_index integer NOT NULL,
                        content text NOT NULL,
                        metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                        created_at timestamptz NOT NULL,
                        embedding vector,
                        embedding_model text
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id
                    ON document_chunks (document_id)
                    """
                )
            conn.commit()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL storage requires installing dependency: psycopg[binary]"
            ) from exc
        return psycopg.connect(self.database_url)


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False)


def _vector_literal(vector: list[float] | None) -> str | None:
    if vector is None:
        return None
    return "[" + ",".join(str(value) for value in vector) + "]"


def _parse_vector_literal(value: str | None) -> list[float] | None:
    if not value:
        return None
    return [float(item) for item in value.strip("[]").split(",") if item]


def _chunk_from_row(row) -> DocumentChunk:
    return DocumentChunk(
        id=row[0],
        document_id=row[1],
        document_name=row[2],
        chunk_index=row[3],
        content=row[4],
        metadata=row[5] or {},
        created_at=row[6].isoformat(),
        embedding=_parse_vector_literal(row[7]),
        embedding_model=row[8],
    )


def _chunk_payload(chunk: DocumentChunk) -> dict:
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "document_name": chunk.document_name,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": chunk.metadata,
        "created_at": chunk.created_at,
        "embedding_model": chunk.embedding_model,
    }
