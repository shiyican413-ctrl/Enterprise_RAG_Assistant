import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from backend.ai_service.core.config import (
    CHUNKS_FILE,
    DATABASE_URL,
    DEFAULT_TENANT_ID,
    DOCUMENTS_FILE,
    INGEST_TASKS_FILE,
)


DocumentStatus = Literal["pending", "processing", "succeeded", "failed"]
TaskStatus = Literal["pending", "processing", "succeeded", "failed"]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class KnowledgeRepository:
    def upsert_document(self, document: dict) -> dict:
        raise NotImplementedError

    def get_document(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        raise NotImplementedError

    def find_document_by_hash(self, file_hash: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        raise NotImplementedError

    def find_document_by_name(self, document_name: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        raise NotImplementedError

    def list_documents(self, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        raise NotImplementedError

    def update_document(self, document_id: str, tenant_id: str, **updates) -> dict | None:
        raise NotImplementedError

    def delete_document(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> bool:
        raise NotImplementedError

    def replace_chunks(self, document_id: str, tenant_id: str, chunks: list[dict]) -> None:
        raise NotImplementedError

    def list_chunks(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        raise NotImplementedError

    def create_task(self, task: dict) -> dict:
        raise NotImplementedError

    def update_task(self, task_id: str, tenant_id: str, **updates) -> dict | None:
        raise NotImplementedError

    def get_task(self, task_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        raise NotImplementedError


class LocalKnowledgeRepository(KnowledgeRepository):
    def __init__(
        self,
        documents_file: Path = DOCUMENTS_FILE,
        chunks_file: Path = CHUNKS_FILE,
        tasks_file: Path = INGEST_TASKS_FILE,
    ) -> None:
        self.documents_file = documents_file
        self.chunks_file = chunks_file
        self.tasks_file = tasks_file
        self.documents_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def upsert_document(self, document: dict) -> dict:
        with self._lock:
            documents = self._load(self.documents_file)
            existing = self._find_index(documents, document["document_id"], document["tenant_id"])
            if existing is None:
                documents.append(document)
            else:
                documents[existing] = {**documents[existing], **document}
            self._save(self.documents_file, documents)
        return document

    def get_document(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        return self._find(self._load(self.documents_file), document_id, tenant_id)

    def find_document_by_hash(self, file_hash: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        for document in self._load(self.documents_file):
            if document.get("tenant_id") == tenant_id and document.get("file_hash") == file_hash:
                return document
        return None

    def find_document_by_name(self, document_name: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        candidates = [
            document
            for document in self._load(self.documents_file)
            if document.get("tenant_id") == tenant_id and document.get("document_name") == document_name
        ]
        candidates.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return candidates[0] if candidates else None

    def list_documents(self, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        documents = [
            document for document in self._load(self.documents_file)
            if document.get("tenant_id") == tenant_id
        ]
        documents.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
        return documents

    def update_document(self, document_id: str, tenant_id: str, **updates) -> dict | None:
        with self._lock:
            documents = self._load(self.documents_file)
            index = self._find_index(documents, document_id, tenant_id)
            if index is None:
                return None
            documents[index].update(updates)
            documents[index]["updated_at"] = utc_now()
            self._save(self.documents_file, documents)
            return documents[index]

    def delete_document(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> bool:
        with self._lock:
            documents = self._load(self.documents_file)
            kept_documents = [
                item for item in documents
                if not (item.get("document_id") == document_id and item.get("tenant_id") == tenant_id)
            ]
            deleted = len(kept_documents) != len(documents)
            self._save(self.documents_file, kept_documents)
            chunks = self._load(self.chunks_file)
            self._save(
                self.chunks_file,
                [
                    item for item in chunks
                    if not (item.get("document_id") == document_id and item.get("tenant_id") == tenant_id)
                ],
            )
            return deleted

    def replace_chunks(self, document_id: str, tenant_id: str, chunks: list[dict]) -> None:
        with self._lock:
            existing = self._load(self.chunks_file)
            kept = [
                item for item in existing
                if not (item.get("document_id") == document_id and item.get("tenant_id") == tenant_id)
            ]
            self._save(self.chunks_file, kept + chunks)

    def list_chunks(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        chunks = [
            chunk for chunk in self._load(self.chunks_file)
            if chunk.get("document_id") == document_id and chunk.get("tenant_id") == tenant_id
        ]
        return sorted(chunks, key=lambda item: int(item.get("chunk_index") or 0))

    def create_task(self, task: dict) -> dict:
        with self._lock:
            tasks = self._load(self.tasks_file)
            tasks.append(task)
            self._save(self.tasks_file, tasks)
        return task

    def update_task(self, task_id: str, tenant_id: str, **updates) -> dict | None:
        with self._lock:
            tasks = self._load(self.tasks_file)
            for task in tasks:
                if task.get("task_id") == task_id and task.get("tenant_id") == tenant_id:
                    task.update(updates)
                    task["updated_at"] = utc_now()
                    self._save(self.tasks_file, tasks)
                    return task
        return None

    def get_task(self, task_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        for task in self._load(self.tasks_file):
            if task.get("task_id") == task_id and task.get("tenant_id") == tenant_id:
                return task
        return None

    def _load(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, path: Path, items: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def _find(self, documents: list[dict], document_id: str, tenant_id: str) -> dict | None:
        index = self._find_index(documents, document_id, tenant_id)
        return documents[index] if index is not None else None

    def _find_index(self, documents: list[dict], document_id: str, tenant_id: str) -> int | None:
        for index, document in enumerate(documents):
            if document.get("document_id") == document_id and document.get("tenant_id") == tenant_id:
                return index
        return None


class PostgresKnowledgeRepository(KnowledgeRepository):
    def __init__(self, database_url: str = DATABASE_URL) -> None:
        if not database_url:
            raise RuntimeError("DATABASE_URL is required for PostgreSQL knowledge metadata")
        self.database_url = database_url
        self._ensure_schema()

    def upsert_document(self, document: dict) -> dict:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO knowledge_documents (
                        id, tenant_id, document_name, source_path, file_hash, extension,
                        size_bytes, version, status, chunk_count, quality_report,
                        metadata, error_message, created_at, updated_at
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s::jsonb,
                        %s::jsonb, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        document_name = EXCLUDED.document_name,
                        source_path = EXCLUDED.source_path,
                        file_hash = EXCLUDED.file_hash,
                        extension = EXCLUDED.extension,
                        size_bytes = EXCLUDED.size_bytes,
                        version = EXCLUDED.version,
                        status = EXCLUDED.status,
                        chunk_count = EXCLUDED.chunk_count,
                        quality_report = EXCLUDED.quality_report,
                        metadata = EXCLUDED.metadata,
                        error_message = EXCLUDED.error_message,
                        updated_at = EXCLUDED.updated_at
                    """,
                    self._document_params(document),
                )
            conn.commit()
        return document

    def get_document(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        return self._fetch_one(
            "WHERE id = %s::uuid AND tenant_id = %s::uuid",
            (document_id, tenant_id),
        )

    def find_document_by_hash(self, file_hash: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        return self._fetch_one(
            "WHERE file_hash = %s AND tenant_id = %s::uuid ORDER BY updated_at DESC LIMIT 1",
            (file_hash, tenant_id),
        )

    def find_document_by_name(self, document_name: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        return self._fetch_one(
            "WHERE document_name = %s AND tenant_id = %s::uuid ORDER BY updated_at DESC LIMIT 1",
            (document_name, tenant_id),
        )

    def list_documents(self, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, tenant_id::text, document_name, source_path, file_hash,
                           extension, size_bytes, version, status, chunk_count,
                           quality_report, metadata, error_message, created_at, updated_at
                    FROM knowledge_documents
                    WHERE tenant_id = %s::uuid
                    ORDER BY updated_at DESC
                    """,
                    (tenant_id,),
                )
                rows = cur.fetchall()
        return [self._document_from_row(row) for row in rows]

    def update_document(self, document_id: str, tenant_id: str, **updates) -> dict | None:
        document = self.get_document(document_id, tenant_id)
        if document is None:
            return None
        document.update(updates)
        document["updated_at"] = utc_now()
        return self.upsert_document(document)

    def delete_document(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM knowledge_documents
                    WHERE id = %s::uuid AND tenant_id = %s::uuid
                    RETURNING id
                    """,
                    (document_id, tenant_id),
                )
                deleted = cur.fetchone() is not None
            conn.commit()
        return deleted

    def replace_chunks(self, document_id: str, tenant_id: str, chunks: list[dict]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM knowledge_chunks WHERE document_id = %s::uuid AND tenant_id = %s::uuid",
                    (document_id, tenant_id),
                )
                for chunk in chunks:
                    cur.execute(
                        """
                        INSERT INTO knowledge_chunks (
                            id, document_id, tenant_id, document_name, chunk_index, content,
                            content_hash, source_page, title_path, block_type, metadata, created_at
                        )
                        VALUES (
                            %s::uuid, %s::uuid, %s::uuid, %s, %s, %s,
                            %s, %s, %s::jsonb, %s, %s::jsonb, %s
                        )
                        """,
                        (
                            chunk["chunk_id"],
                            chunk["document_id"],
                            chunk["tenant_id"],
                            chunk["document_name"],
                            chunk["chunk_index"],
                            chunk["content"],
                            chunk["hash"],
                            chunk.get("source_page"),
                            json.dumps(chunk.get("title_path") or [], ensure_ascii=False),
                            chunk.get("block_type"),
                            json.dumps(chunk.get("metadata") or {}, ensure_ascii=False),
                            chunk["created_at"],
                        ),
                    )
            conn.commit()

    def list_chunks(self, document_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, document_id::text, tenant_id::text, document_name,
                           chunk_index, content, content_hash, source_page, title_path,
                           block_type, metadata, created_at
                    FROM knowledge_chunks
                    WHERE document_id = %s::uuid AND tenant_id = %s::uuid
                    ORDER BY chunk_index ASC
                    """,
                    (document_id, tenant_id),
                )
                rows = cur.fetchall()
        return [self._chunk_from_row(row) for row in rows]

    def create_task(self, task: dict) -> dict:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO knowledge_ingest_tasks (
                        id, document_id, tenant_id, status, current_step, progress,
                        error_message, created_at, updated_at, started_at, finished_at
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        task["task_id"],
                        task["document_id"],
                        task["tenant_id"],
                        task["status"],
                        task.get("current_step"),
                        task.get("progress", 0),
                        task.get("error_message"),
                        task["created_at"],
                        task["updated_at"],
                        task.get("started_at"),
                        task.get("finished_at"),
                    ),
                )
            conn.commit()
        return task

    def update_task(self, task_id: str, tenant_id: str, **updates) -> dict | None:
        task = self.get_task(task_id, tenant_id)
        if task is None:
            return None
        task.update(updates)
        task["updated_at"] = utc_now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE knowledge_ingest_tasks
                    SET status = %s, current_step = %s, progress = %s,
                        error_message = %s, updated_at = %s, started_at = %s,
                        finished_at = %s
                    WHERE id = %s::uuid AND tenant_id = %s::uuid
                    """,
                    (
                        task["status"],
                        task.get("current_step"),
                        task.get("progress", 0),
                        task.get("error_message"),
                        task["updated_at"],
                        task.get("started_at"),
                        task.get("finished_at"),
                        task_id,
                        tenant_id,
                    ),
                )
            conn.commit()
        return task

    def get_task(self, task_id: str, tenant_id: str = DEFAULT_TENANT_ID) -> dict | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, document_id::text, tenant_id::text, status,
                           current_step, progress, error_message, created_at, updated_at,
                           started_at, finished_at
                    FROM knowledge_ingest_tasks
                    WHERE id = %s::uuid AND tenant_id = %s::uuid
                    """,
                    (task_id, tenant_id),
                )
                row = cur.fetchone()
        return self._task_from_row(row) if row else None

    def _fetch_one(self, where_sql: str, params: tuple) -> dict | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, tenant_id::text, document_name, source_path, file_hash,
                           extension, size_bytes, version, status, chunk_count,
                           quality_report, metadata, error_message, created_at, updated_at
                    FROM knowledge_documents
                    {where_sql}
                    """,
                    params,
                )
                row = cur.fetchone()
        return self._document_from_row(row) if row else None

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_documents (
                        id uuid PRIMARY KEY,
                        tenant_id uuid NOT NULL,
                        document_name text NOT NULL,
                        source_path text NOT NULL,
                        file_hash text NOT NULL,
                        extension text NOT NULL,
                        size_bytes bigint NOT NULL DEFAULT 0,
                        version integer NOT NULL DEFAULT 1,
                        status text NOT NULL,
                        chunk_count integer NOT NULL DEFAULT 0,
                        quality_report jsonb NOT NULL DEFAULT '{}'::jsonb,
                        metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                        error_message text,
                        created_at timestamptz NOT NULL,
                        updated_at timestamptz NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_chunks (
                        id uuid PRIMARY KEY,
                        document_id uuid NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                        tenant_id uuid NOT NULL,
                        document_name text NOT NULL,
                        chunk_index integer NOT NULL,
                        content text NOT NULL,
                        content_hash text NOT NULL,
                        source_page integer,
                        title_path jsonb NOT NULL DEFAULT '[]'::jsonb,
                        block_type text,
                        metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                        created_at timestamptz NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_ingest_tasks (
                        id uuid PRIMARY KEY,
                        document_id uuid NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
                        tenant_id uuid NOT NULL,
                        status text NOT NULL,
                        current_step text,
                        progress integer NOT NULL DEFAULT 0,
                        error_message text,
                        created_at timestamptz NOT NULL,
                        updated_at timestamptz NOT NULL,
                        started_at timestamptz,
                        finished_at timestamptz
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_documents_tenant_hash
                    ON knowledge_documents (tenant_id, file_hash)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
                    ON knowledge_chunks (tenant_id, document_id, chunk_index)
                    """
                )
            conn.commit()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL knowledge metadata requires installing dependency: psycopg[binary]"
            ) from exc
        return psycopg.connect(self.database_url)

    def _document_params(self, document: dict) -> tuple:
        return (
            document["document_id"],
            document["tenant_id"],
            document["document_name"],
            document["source_path"],
            document["file_hash"],
            document["extension"],
            document.get("size_bytes", 0),
            document.get("version", 1),
            document.get("status", "pending"),
            document.get("chunk_count", 0),
            json.dumps(document.get("quality_report") or {}, ensure_ascii=False),
            json.dumps(document.get("metadata") or {}, ensure_ascii=False),
            document.get("error_message"),
            document["created_at"],
            document["updated_at"],
        )

    def _document_from_row(self, row) -> dict:
        return {
            "document_id": row[0],
            "tenant_id": row[1],
            "document_name": row[2],
            "source_path": row[3],
            "file_hash": row[4],
            "extension": row[5],
            "size_bytes": row[6],
            "version": row[7],
            "status": row[8],
            "chunk_count": row[9],
            "quality_report": row[10] or {},
            "metadata": row[11] or {},
            "error_message": row[12],
            "created_at": row[13].isoformat(),
            "updated_at": row[14].isoformat(),
        }

    def _chunk_from_row(self, row) -> dict:
        return {
            "chunk_id": row[0],
            "document_id": row[1],
            "tenant_id": row[2],
            "document_name": row[3],
            "chunk_index": row[4],
            "content": row[5],
            "hash": row[6],
            "source_page": row[7],
            "title_path": row[8] or [],
            "block_type": row[9],
            "metadata": row[10] or {},
            "created_at": row[11].isoformat(),
        }

    def _task_from_row(self, row) -> dict:
        return {
            "task_id": row[0],
            "document_id": row[1],
            "tenant_id": row[2],
            "status": row[3],
            "current_step": row[4],
            "progress": row[5],
            "error_message": row[6],
            "created_at": row[7].isoformat(),
            "updated_at": row[8].isoformat(),
            "started_at": row[9].isoformat() if row[9] else None,
            "finished_at": row[10].isoformat() if row[10] else None,
        }


def create_knowledge_repository() -> KnowledgeRepository:
    if DATABASE_URL:
        return PostgresKnowledgeRepository(DATABASE_URL)
    return LocalKnowledgeRepository()


def new_id() -> str:
    return str(uuid.uuid4())
