import hashlib
import shutil
from pathlib import Path

from fastapi import UploadFile

from backend.ai_service.core.config import (
    CHUNK_OVERLAP, CHUNK_SIZE, DEFAULT_TENANT_ID, SUPPORTED_EXTENSIONS, UPLOAD_DIR,
)
from backend.ai_service.knowledge.ingest_quality_service import IngestQualityService
from backend.ai_service.knowledge.loaders.document_loader import load_document_text
from backend.ai_service.storage.factory import create_vector_store
from backend.ai_service.knowledge.splitter import split_text


class KnowledgeService:
    def __init__(
        self,
        vector_store=None,
        quality_service: IngestQualityService | None = None,
    ) -> None:
        self.vector_store = vector_store or create_vector_store()
        self.quality_service = quality_service or IngestQualityService()
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async def ingest_upload(self, file: UploadFile, tenant_id: str) -> dict:
        filename = Path(file.filename or "uploaded.txt").name
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {suffix}")

        content = await file.read()
        digest = hashlib.md5(content).hexdigest()
        tenant_upload_dir = UPLOAD_DIR / tenant_id
        tenant_upload_dir.mkdir(parents=True, exist_ok=True)
        target = tenant_upload_dir / f"{digest}_{filename}"
        target.write_bytes(content)
        return self.ingest_file(
            target, original_name=filename, file_md5=digest, tenant_id=tenant_id
        )

    def ingest_file(
        self,
        path: Path,
        original_name: str | None = None,
        file_md5: str | None = None,
        tenant_id: str = DEFAULT_TENANT_ID,
    ) -> dict:
        text = load_document_text(path)
        chunks = split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        embedding_client = getattr(self.vector_store, "embedding_client", None)
        quality_report = self.quality_service.inspect_chunks(
            chunks,
            embedding_ready=bool(getattr(embedding_client, "enabled", False)),
        )
        document_name = original_name or path.name
        document_id, chunk_count = self.vector_store.add_document(
            document_name=document_name,
            chunks=chunks,
            metadata={
                "source_path": str(path),
                "file_md5": file_md5 or _file_md5(path),
                "extension": path.suffix.lower(),
                "tenant_id": tenant_id,
            },
            tenant_id=tenant_id,
        )

        return {
            "document_id": document_id,
            "document_name": document_name,
            "chunk_count": chunk_count,
            "quality_report": quality_report.to_dict(),
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


def _file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()
