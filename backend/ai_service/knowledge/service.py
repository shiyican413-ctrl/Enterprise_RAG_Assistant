import hashlib
import shutil
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, UploadFile

from backend.ai_service.core.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_TENANT_ID,
    SUPPORTED_EXTENSIONS,
    UPLOAD_DIR,
)
from backend.ai_service.knowledge.ingest_quality_service import IngestQualityService
from backend.ai_service.knowledge.parser_service import DocumentParserService
from backend.ai_service.knowledge.repository import (
    KnowledgeRepository,
    create_knowledge_repository,
    new_id,
    utc_now,
)
from backend.ai_service.knowledge.splitter import TextChunk, split_text
from backend.ai_service.storage.factory import create_vector_store


class KnowledgeService:
    def __init__(
        self,
        vector_store=None,
        quality_service: IngestQualityService | None = None,
        repository: KnowledgeRepository | None = None,
        parser_service: DocumentParserService | None = None,
    ) -> None:
        self.vector_store = vector_store or create_vector_store()
        self.quality_service = quality_service or IngestQualityService()
        self.repository = repository or create_knowledge_repository()
        self.parser_service = parser_service or DocumentParserService()
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async def ingest_upload(
        self,
        file: UploadFile,
        tenant_id: str,
        user_id: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict:
        filename = Path(file.filename or "uploaded.txt").name
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {suffix}")

        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        tenant_upload_dir = UPLOAD_DIR / tenant_id
        tenant_upload_dir.mkdir(parents=True, exist_ok=True)
        target = tenant_upload_dir / f"{file_hash}_{filename}"
        target.write_bytes(content)

        duplicate = self.repository.find_document_by_hash(file_hash, tenant_id=tenant_id)
        if duplicate and duplicate.get("status") == "succeeded":
            task = self._create_task(
                document_id=duplicate["document_id"],
                tenant_id=tenant_id,
                status="succeeded",
                current_step="deduplicated",
                progress=100,
                finished=True,
            )
            return {
                "message": "document already ingested",
                "duplicate": True,
                "task_id": task["task_id"],
                **_document_response(duplicate),
            }

        existing_by_name = self.repository.find_document_by_name(filename, tenant_id=tenant_id)
        document_id = (
            existing_by_name["document_id"]
            if existing_by_name is not None
            else new_id()
        )
        version = int(existing_by_name.get("version", 0)) + 1 if existing_by_name else 1
        now = utc_now()
        document = {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "document_name": filename,
            "source_path": str(target),
            "file_hash": file_hash,
            "extension": suffix,
            "size_bytes": len(content),
            "version": version,
            "status": "pending",
            "chunk_count": 0,
            "quality_report": {},
            "metadata": {
                "source_type": "file",
                "uploaded_by": user_id,
            },
            "error_message": None,
            "created_at": existing_by_name.get("created_at") if existing_by_name else now,
            "updated_at": now,
        }
        self.repository.upsert_document(document)
        task = self._create_task(
            document_id=document_id,
            tenant_id=tenant_id,
            status="pending",
            current_step="queued",
            progress=0,
        )

        if background_tasks is not None:
            background_tasks.add_task(
                self.process_ingest_task,
                task["task_id"],
                document_id,
                target,
                filename,
                file_hash,
                tenant_id,
            )
        else:
            self.process_ingest_task(
                task["task_id"],
                document_id,
                target,
                filename,
                file_hash,
                tenant_id,
            )

        return {
            "message": "document ingestion queued",
            "duplicate": False,
            "task_id": task["task_id"],
            **_document_response(document),
        }

    def process_ingest_task(
        self,
        task_id: str,
        document_id: str,
        path: Path,
        document_name: str,
        file_hash: str,
        tenant_id: str,
    ) -> None:
        try:
            self._mark_processing(task_id, document_id, tenant_id, "parse_document", 10)
            text = self.parser_service.parse(path)

            self._mark_processing(task_id, document_id, tenant_id, "split_chunks", 35)
            chunks = split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
            enriched_chunks = _enrich_chunks(
                chunks,
                document_id=document_id,
                document_name=document_name,
                tenant_id=tenant_id,
            )

            self._mark_processing(task_id, document_id, tenant_id, "quality_check", 50)
            embedding_client = getattr(self.vector_store, "embedding_client", None)
            quality_report = self.quality_service.inspect_chunks(
                chunks,
                embedding_ready=bool(getattr(embedding_client, "enabled", False)),
            )
            self.quality_service.ensure_usable(quality_report)

            self._mark_processing(task_id, document_id, tenant_id, "write_vector_store", 70)
            self.vector_store.delete_document(document_id, tenant_id=tenant_id)
            _, chunk_count = self.vector_store.add_document(
                document_name=document_name,
                chunks=[
                    TextChunk(
                        text=chunk["content"],
                        chunk_index=chunk["chunk_index"],
                        metadata=chunk["metadata"],
                    )
                    for chunk in enriched_chunks
                ],
                metadata={
                    "source_path": str(path),
                    "file_hash": file_hash,
                    "file_md5": _file_md5(path),
                    "extension": path.suffix.lower(),
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                },
                tenant_id=tenant_id,
                document_id=document_id,
            )

            self._mark_processing(task_id, document_id, tenant_id, "write_metadata", 90)
            self.repository.replace_chunks(document_id, tenant_id, enriched_chunks)
            self.repository.update_document(
                document_id,
                tenant_id,
                status="succeeded",
                chunk_count=chunk_count,
                quality_report=quality_report.to_dict(),
                error_message=None,
            )
            self.repository.update_task(
                task_id,
                tenant_id,
                status="succeeded",
                current_step="completed",
                progress=100,
                finished_at=utc_now(),
            )
        except Exception as exc:
            self.repository.update_document(
                document_id,
                tenant_id,
                status="failed",
                error_message=str(exc),
            )
            self.repository.update_task(
                task_id,
                tenant_id,
                status="failed",
                current_step="failed",
                progress=100,
                error_message=str(exc),
                finished_at=utc_now(),
            )
            raise

    def ingest_file(
        self,
        path: Path,
        original_name: str | None = None,
        file_md5: str | None = None,
        tenant_id: str = DEFAULT_TENANT_ID,
    ) -> dict:
        content = path.read_bytes()
        file_hash = hashlib.sha256(content).hexdigest()
        document_name = original_name or path.name
        existing_by_name = self.repository.find_document_by_name(document_name, tenant_id=tenant_id)
        document_id = existing_by_name["document_id"] if existing_by_name else new_id()
        version = int(existing_by_name.get("version", 0)) + 1 if existing_by_name else 1
        now = utc_now()
        document = {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "document_name": document_name,
            "source_path": str(path),
            "file_hash": file_hash,
            "extension": path.suffix.lower(),
            "size_bytes": len(content),
            "version": version,
            "status": "pending",
            "chunk_count": 0,
            "quality_report": {},
            "metadata": {"source_type": "file"},
            "error_message": None,
            "created_at": existing_by_name.get("created_at") if existing_by_name else now,
            "updated_at": now,
        }
        self.repository.upsert_document(document)
        task = self._create_task(
            document_id=document_id,
            tenant_id=tenant_id,
            status="pending",
            current_step="queued",
            progress=0,
        )
        self.process_ingest_task(
            task["task_id"],
            document_id,
            path,
            document_name,
            file_hash,
            tenant_id,
        )
        completed = self.repository.get_document(document_id, tenant_id) or document
        return {
            "task_id": task["task_id"],
            "duplicate": False,
            **_document_response(completed),
        }

    def ingest_directory(self, directory: Path, tenant_id: str) -> list[dict]:
        results: list[dict] = []
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                tenant_upload_dir = UPLOAD_DIR / tenant_id
                tenant_upload_dir.mkdir(parents=True, exist_ok=True)
                copied = tenant_upload_dir / path.name
                if path.resolve() != copied.resolve():
                    shutil.copy2(path, copied)
                results.append(self.ingest_file(
                    copied, original_name=path.name, tenant_id=tenant_id
                ))
        return results

    def list_documents(self, tenant_id: str) -> list[dict]:
        return [_document_response(document) for document in self.repository.list_documents(tenant_id)]

    def list_document_chunks(self, document_id: str, tenant_id: str) -> list[dict]:
        chunks = self.repository.list_chunks(document_id, tenant_id)
        if chunks:
            return chunks
        return self.vector_store.list_document_chunks(document_id, tenant_id=tenant_id)

    def delete_document(self, document_id: str, tenant_id: str) -> int:
        deleted_chunks = self.vector_store.delete_document(document_id, tenant_id=tenant_id)
        metadata_deleted = self.repository.delete_document(document_id, tenant_id)
        return deleted_chunks if deleted_chunks else int(metadata_deleted)

    def delete_documents(self, document_ids: list[str], tenant_id: str) -> int:
        deleted_chunks = self.vector_store.delete_documents(document_ids, tenant_id=tenant_id)
        metadata_deleted = 0
        for document_id in document_ids:
            metadata_deleted += int(self.repository.delete_document(document_id, tenant_id))
        return deleted_chunks if deleted_chunks else metadata_deleted

    def clear(self, tenant_id: str) -> None:
        self.vector_store.clear(tenant_id=tenant_id)
        for document in self.repository.list_documents(tenant_id):
            self.repository.delete_document(document["document_id"], tenant_id)

    def get_task(self, task_id: str, tenant_id: str) -> dict | None:
        return self.repository.get_task(task_id, tenant_id)

    def _create_task(
        self,
        *,
        document_id: str,
        tenant_id: str,
        status: str,
        current_step: str,
        progress: int,
        finished: bool = False,
    ) -> dict:
        now = utc_now()
        task = {
            "task_id": new_id(),
            "document_id": document_id,
            "tenant_id": tenant_id,
            "status": status,
            "current_step": current_step,
            "progress": progress,
            "error_message": None,
            "created_at": now,
            "updated_at": now,
            "started_at": now if status != "pending" else None,
            "finished_at": now if finished else None,
        }
        return self.repository.create_task(task)

    def _mark_processing(
        self,
        task_id: str,
        document_id: str,
        tenant_id: str,
        current_step: str,
        progress: int,
    ) -> None:
        task = self.repository.get_task(task_id, tenant_id)
        self.repository.update_task(
            task_id,
            tenant_id,
            status="processing",
            current_step=current_step,
            progress=progress,
            started_at=task.get("started_at") if task else utc_now(),
        )
        self.repository.update_document(document_id, tenant_id, status="processing")


def _enrich_chunks(
    chunks: list[TextChunk],
    *,
    document_id: str,
    document_name: str,
    tenant_id: str,
) -> list[dict]:
    now = utc_now()
    enriched: list[dict] = []
    for index, chunk in enumerate(chunks):
        metadata = dict(chunk.metadata)
        source_page = metadata.get("page_start") or metadata.get("page")
        title_path = list(metadata.get("section_path") or [])
        block_type = metadata.get("chunk_type", "paragraph")
        content_hash = _chunk_hash(chunk.text, metadata)
        metadata.update(
            {
                "source_page": source_page,
                "title_path": title_path,
                "block_type": block_type,
                "hash": content_hash,
            }
        )
        retrieval_text = _retrieval_text(chunk.text, title_path, block_type)
        enriched.append(
            {
                "chunk_id": new_id(),
                "document_id": document_id,
                "tenant_id": tenant_id,
                "document_name": document_name,
                "chunk_index": index,
                "content": chunk.text,
                "retrieval_text": retrieval_text,
                "hash": content_hash,
                "source_page": source_page,
                "title_path": title_path,
                "block_type": block_type,
                "metadata": metadata,
                "created_at": now,
            }
        )
    return enriched


def _chunk_hash(content: str, metadata: dict[str, Any]) -> str:
    payload = {
        "content": " ".join(content.split()),
        "section_path": metadata.get("section_path") or [],
        "chunk_type": metadata.get("chunk_type"),
        "page_start": metadata.get("page_start"),
    }
    return hashlib.sha256(
        json_dumps(payload).encode("utf-8")
    ).hexdigest()


def _retrieval_text(content: str, title_path: list[str], block_type: str) -> str:
    context = " > ".join(title_path)
    prefixes = []
    if context:
        prefixes.append(f"标题路径：{context}")
    if block_type:
        prefixes.append(f"内容类型：{block_type}")
    return "\n".join([*prefixes, content]).strip()


def json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _document_response(document: dict) -> dict:
    return {
        "document_id": document["document_id"],
        "document_name": document["document_name"],
        "tenant_id": document.get("tenant_id"),
        "source_path": document.get("source_path"),
        "file_hash": document.get("file_hash"),
        "extension": document.get("extension"),
        "size_bytes": document.get("size_bytes", 0),
        "version": document.get("version", 1),
        "status": document.get("status", "pending"),
        "chunk_count": document.get("chunk_count", 0),
        "quality_report": document.get("quality_report") or {},
        "metadata": document.get("metadata") or {},
        "error_message": document.get("error_message"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }


def _file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()
