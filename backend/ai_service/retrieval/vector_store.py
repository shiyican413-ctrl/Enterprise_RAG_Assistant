import json
import math
import re
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from backend.ai_service.core.config import (
    EMBEDDING_DIMENSIONS,
    INDEX_FILE,
    KNOWLEDGE_DIR,
    MILVUS_COLLECTION,
    MILVUS_DB_NAME,
    MILVUS_TOKEN,
    MILVUS_URI,
    VECTOR_SCORE_THRESHOLD,
    DEFAULT_TENANT_ID,
)
from backend.ai_service.retrieval.embeddings import BailianEmbeddingClient


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
    tenant_id: str = DEFAULT_TENANT_ID
    embedding: list[float] | None = None
    embedding_model: str | None = None


@dataclass
class SearchResult:
    chunk: DocumentChunk
    score: float


@dataclass(frozen=True)
class _PreparedChunk:
    content: str
    metadata: dict


class LocalVectorStore:
    """Small persistent vector store with Bailian dense embeddings and sparse fallback."""

    def __init__(
        self,
        index_file: Path = INDEX_FILE,
        embedding_client: BailianEmbeddingClient | None = None,
        score_threshold: float = VECTOR_SCORE_THRESHOLD,
    ) -> None:
        self.index_file = index_file
        self.embedding_client = embedding_client or BailianEmbeddingClient()
        self.score_threshold = score_threshold
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        self._chunks: list[DocumentChunk] = self._load()

    def add_document(
        self,
        document_name: str,
        chunks: Iterable[str],
        metadata: dict | None = None,
        tenant_id: str = DEFAULT_TENANT_ID,
    ) -> tuple[str, int]:
        document_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        prepared_chunks = _prepare_chunks(chunks, metadata)
        contents = [chunk.content for chunk in prepared_chunks]
        embeddings = self._embed_contents(contents)

        new_chunks = [
            DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                document_name=document_name,
                tenant_id=tenant_id,
                chunk_index=index,
                content=chunk.content,
                metadata=chunk.metadata,
                created_at=now,
                embedding=embeddings[index] if embeddings else None,
                embedding_model=self.embedding_client.model if embeddings else None,
            )
            for index, chunk in enumerate(prepared_chunks)
        ]

        self._chunks.extend(new_chunks)
        self._save()
        return document_id, len(new_chunks)

    def list_documents(self, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        documents: dict[str, dict] = {}
        for chunk in self._chunks:
            if chunk.tenant_id != tenant_id:
                continue
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

    def delete_document(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> int:
        before = len(self._chunks)
        self._chunks = [chunk for chunk in self._chunks if not (
            chunk.document_id == document_id and chunk.tenant_id == tenant_id
        )]
        deleted = before - len(self._chunks)
        if deleted:
            self._save()
        return deleted

    def delete_documents(self, document_ids: Iterable[str], tenant_id: str = DEFAULT_TENANT_ID) -> int:
        id_set = set(document_ids)
        before = len(self._chunks)
        self._chunks = [chunk for chunk in self._chunks if not (
            chunk.document_id in id_set and chunk.tenant_id == tenant_id
        )]
        deleted = before - len(self._chunks)
        if deleted:
            self._save()
        return deleted

    def list_document_chunks(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        chunks = [
            chunk
            for chunk in self._chunks
            if chunk.document_id == document_id and chunk.tenant_id == tenant_id
        ]
        return [_chunk_payload(chunk) for chunk in sorted(chunks, key=lambda item: item.chunk_index)]

    def clear(self, tenant_id: str = DEFAULT_TENANT_ID) -> None:
        self._chunks = [chunk for chunk in self._chunks if chunk.tenant_id != tenant_id]
        self._save()

    def search(self, query: str, top_k: int, tenant_id: str = DEFAULT_TENANT_ID) -> list[SearchResult]:
        if self.embedding_client.enabled and self._has_dense_embeddings():
            return self._dense_search(query, top_k=top_k, tenant_id=tenant_id)
        return self._sparse_search(query, top_k=top_k, tenant_id=tenant_id)

    def _dense_search(self, query: str, top_k: int, tenant_id: str) -> list[SearchResult]:
        query_embedding = self.embedding_client.embed_texts([query])[0]
        results: list[SearchResult] = []
        for chunk in self._chunks:
            if chunk.tenant_id != tenant_id:
                continue
            if not chunk.embedding:
                continue
            score = _dense_cosine_similarity(query_embedding, chunk.embedding)
            if score >= self.score_threshold:
                results.append(SearchResult(chunk=chunk, score=score))

        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def _sparse_search(self, query: str, top_k: int, tenant_id: str) -> list[SearchResult]:
        query_vector = _to_vector(query)
        if not query_vector:
            return []

        results: list[SearchResult] = []
        for chunk in self._chunks:
            if chunk.tenant_id != tenant_id:
                continue
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
        migrated = []
        for item in payload:
            item.setdefault("tenant_id", DEFAULT_TENANT_ID)
            migrated.append(DocumentChunk(**item))
        return migrated

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


class MilvusVectorStore:
    """Milvus backed vector store for document chunks and dense retrieval."""

    _OUTPUT_FIELDS = [
        "id",
        "document_id",
        "document_name",
        "tenant_id",
        "chunk_index",
        "content",
        "metadata_json",
        "created_at",
        "embedding_model",
    ]

    def __init__(
        self,
        uri: str = MILVUS_URI,
        token: str = MILVUS_TOKEN,
        db_name: str = MILVUS_DB_NAME,
        collection_name: str = MILVUS_COLLECTION,
        embedding_client: BailianEmbeddingClient | None = None,
        score_threshold: float = VECTOR_SCORE_THRESHOLD,
        dimensions: int = EMBEDDING_DIMENSIONS,
    ) -> None:
        if not uri:
            raise RuntimeError("MILVUS_URI is required for Milvus storage")
        self.uri = uri
        self.token = token
        self.db_name = db_name
        self.collection_name = collection_name
        self.embedding_client = embedding_client or BailianEmbeddingClient()
        self.score_threshold = score_threshold
        self.dimensions = dimensions
        self.alias = f"enterprise_rag_{uuid.uuid4().hex}"
        self.collection = self._ensure_collection()

    def add_document(
        self,
        document_name: str,
        chunks: Iterable[str],
        metadata: dict | None = None,
        tenant_id: str = DEFAULT_TENANT_ID,
    ) -> tuple[str, int]:
        prepared_chunks = _prepare_chunks(chunks, metadata)
        contents = [chunk.content for chunk in prepared_chunks]
        if not prepared_chunks:
            return str(uuid.uuid4()), 0

        embeddings = self._embed_contents(contents)
        document_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        rows = [
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "document_name": document_name,
                "tenant_id": tenant_id,
                "chunk_index": index,
                "content": chunk.content,
                "metadata_json": _json(chunk.metadata),
                "created_at": now,
                "embedding": embeddings[index],
                "embedding_model": self.embedding_client.model,
            }
            for index, chunk in enumerate(prepared_chunks)
        ]

        self.collection.insert(rows)
        self.collection.flush()
        return document_id, len(rows)

    def list_documents(self, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        chunks = self._query_chunks(self._tenant_expr(tenant_id))
        documents: dict[str, dict] = {}
        for chunk in chunks:
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

    def delete_document(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> int:
        expr = f'{self._tenant_expr(tenant_id)} and document_id == "{_escape_milvus_string(document_id)}"'
        chunks = self._query_chunks(expr)
        if not chunks:
            return 0
        result = self.collection.delete(expr)
        self.collection.flush()
        return int(getattr(result, "delete_count", len(chunks)) or len(chunks))

    def delete_documents(self, document_ids: Iterable[str], tenant_id: str = DEFAULT_TENANT_ID) -> int:
        ids = list(document_ids)
        if not ids:
            return 0
        escaped = [_escape_milvus_string(document_id) for document_id in ids]
        ids_expr = " or ".join(f'document_id == "{document_id}"' for document_id in escaped)
        expr = f'{self._tenant_expr(tenant_id)} and ({ids_expr})'
        chunks = self._query_chunks(expr)
        if not chunks:
            return 0
        result = self.collection.delete(expr)
        self.collection.flush()
        return int(getattr(result, "delete_count", len(chunks)) or len(chunks))

    def list_document_chunks(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        expr = f'{self._tenant_expr(tenant_id)} and document_id == "{_escape_milvus_string(document_id)}"'
        chunks = self._query_chunks(expr)
        return [_chunk_payload(chunk) for chunk in sorted(chunks, key=lambda item: item.chunk_index)]

    def clear(self, tenant_id: str = DEFAULT_TENANT_ID) -> None:
        if self.collection.num_entities == 0:
            return
        self.collection.delete(self._tenant_expr(tenant_id))
        self.collection.flush()

    def search(self, query: str, top_k: int, tenant_id: str = DEFAULT_TENANT_ID) -> list[SearchResult]:
        query_embedding = self.embedding_client.embed_texts([query])[0]
        hits = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=top_k,
            output_fields=self._OUTPUT_FIELDS,
            expr=self._tenant_expr(tenant_id),
        )
        results: list[SearchResult] = []
        for hit in hits[0]:
            score = float(hit.score or 0)
            if score < self.score_threshold:
                continue
            entity = hit.entity
            chunk = DocumentChunk(
                id=str(entity.get("id")),
                document_id=str(entity.get("document_id")),
                document_name=str(entity.get("document_name")),
                tenant_id=str(entity.get("tenant_id")),
                chunk_index=int(entity.get("chunk_index")),
                content=str(entity.get("content")),
                metadata=_loads_metadata(entity.get("metadata_json")),
                created_at=str(entity.get("created_at")),
                embedding=None,
                embedding_model=entity.get("embedding_model"),
            )
            results.append(SearchResult(chunk=chunk, score=score))
        return results

    def _embed_contents(self, contents: list[str]) -> list[list[float]]:
        if not contents:
            return []
        if not self.embedding_client.enabled:
            raise RuntimeError("DASHSCOPE_API_KEY is required for Milvus document ingestion")
        embeddings = self.embedding_client.embed_texts(contents)
        invalid = [len(embedding) for embedding in embeddings if len(embedding) != self.dimensions]
        if invalid:
            raise RuntimeError(
                f"Milvus collection expects {self.dimensions}-dim embeddings, got {invalid[0]}"
            )
        return embeddings

    def _query_chunks(self, expr: str) -> list[DocumentChunk]:
        rows = self.collection.query(
            expr=expr,
            output_fields=self._OUTPUT_FIELDS,
            limit=16384,
        )
        return [_chunk_from_milvus_row(row) for row in rows]

    @staticmethod
    def _tenant_expr(tenant_id: str) -> str:
        return f'tenant_id == "{_escape_milvus_string(tenant_id)}"'

    def _ensure_collection(self):
        try:
            from pymilvus import (
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                connections,
                utility,
            )
        except ImportError as exc:
            raise RuntimeError("Milvus storage requires installing dependency: pymilvus") from exc

        connect_kwargs = {"alias": self.alias, "uri": self.uri}
        if self.token:
            connect_kwargs["token"] = self.token
        if self.db_name:
            connect_kwargs["db_name"] = self.db_name
        connections.connect(**connect_kwargs)

        if utility.has_collection(self.collection_name, using=self.alias):
            existing = Collection(name=self.collection_name, using=self.alias)
            if "tenant_id" not in {field.name for field in existing.schema.fields}:
                self.collection_name = f"{self.collection_name}_tenant_v1"

        if not utility.has_collection(self.collection_name, using=self.alias):
            fields = [
                FieldSchema("id", DataType.VARCHAR, is_primary=True, max_length=64),
                FieldSchema("document_id", DataType.VARCHAR, max_length=64),
                FieldSchema("document_name", DataType.VARCHAR, max_length=512),
                FieldSchema("tenant_id", DataType.VARCHAR, max_length=64),
                FieldSchema("chunk_index", DataType.INT64),
                FieldSchema("content", DataType.VARCHAR, max_length=65535),
                FieldSchema("metadata_json", DataType.VARCHAR, max_length=8192),
                FieldSchema("created_at", DataType.VARCHAR, max_length=64),
                FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=self.dimensions),
                FieldSchema("embedding_model", DataType.VARCHAR, max_length=256),
            ]
            schema = CollectionSchema(
                fields=fields,
                description="Enterprise RAG document chunks",
            )
            collection = Collection(
                name=self.collection_name,
                schema=schema,
                using=self.alias,
                consistency_level="Strong",
            )
            collection.create_index(
                field_name="embedding",
                index_params={
                    "index_type": "IVF_FLAT",
                    "metric_type": "COSINE",
                    "params": {"nlist": 128},
                },
            )
        else:
            collection = Collection(
                name=self.collection_name,
                using=self.alias,
                consistency_level="Strong",
            )

        collection.load()
        return collection


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False)


def _prepare_chunks(
    chunks: Iterable[Any],
    base_metadata: dict | None = None,
) -> list[_PreparedChunk]:
    prepared: list[_PreparedChunk] = []
    document_metadata = dict(base_metadata or {})
    for item in chunks:
        if isinstance(item, str):
            content = item
            chunk_metadata: dict = {}
        else:
            content = str(getattr(item, "text", getattr(item, "content", "")) or "")
            raw_metadata = getattr(item, "metadata", {}) or {}
            chunk_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}

        content = content.strip()
        if not content:
            continue
        prepared.append(
            _PreparedChunk(
                content=content,
                metadata={**document_metadata, **chunk_metadata},
            )
        )
    return prepared


def _chunk_from_milvus_row(row: dict) -> DocumentChunk:
    return DocumentChunk(
        id=str(row["id"]),
        document_id=str(row["document_id"]),
        document_name=str(row["document_name"]),
        tenant_id=str(row["tenant_id"]),
        chunk_index=int(row["chunk_index"]),
        content=str(row["content"]),
        metadata=_loads_metadata(row.get("metadata_json")),
        created_at=str(row["created_at"]),
        embedding=None,
        embedding_model=row.get("embedding_model"),
    )


def _loads_metadata(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _escape_milvus_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _chunk_payload(chunk: DocumentChunk) -> dict:
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "document_name": chunk.document_name,
        "tenant_id": chunk.tenant_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": chunk.metadata,
        "created_at": chunk.created_at,
        "embedding_model": chunk.embedding_model,
    }
