import hashlib
import shutil
from pathlib import Path

from fastapi import UploadFile

from backend.ai_service.config import CHUNK_OVERLAP, CHUNK_SIZE, SUPPORTED_EXTENSIONS, UPLOAD_DIR
from backend.ai_service.loaders.document_loader import load_document_text
from backend.ai_service.services.text_splitter import split_text
from backend.ai_service.services.vector_store_service import PostgresVectorStore


class KnowledgeService:
    def __init__(self, vector_store: PostgresVectorStore | None = None) -> None:
        self.vector_store = vector_store or PostgresVectorStore()
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async def ingest_upload(self, file: UploadFile) -> dict:
        filename = Path(file.filename or "uploaded.txt").name
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {suffix}")

        content = await file.read()
        digest = hashlib.md5(content).hexdigest()
        target = UPLOAD_DIR / f"{digest}_{filename}"
        target.write_bytes(content)
        return self.ingest_file(target, original_name=filename, file_md5=digest)

    def ingest_file(
        self,
        path: Path,
        original_name: str | None = None,
        file_md5: str | None = None,
    ) -> dict:
        text = load_document_text(path)
        chunks = split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        document_name = original_name or path.name
        document_id, chunk_count = self.vector_store.add_document(
            document_name=document_name,
            chunks=[chunk.text for chunk in chunks],
            metadata={
                "source_path": str(path),
                "file_md5": file_md5 or _file_md5(path),
                "extension": path.suffix.lower(),
            },
        )

        return {
            "document_id": document_id,
            "document_name": document_name,
            "chunk_count": chunk_count,
        }

    def ingest_directory(self, directory: Path) -> list[dict]:
        results: list[dict] = []
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                copied = UPLOAD_DIR / path.name
                if path.resolve() != copied.resolve():
                    shutil.copy2(path, copied)
                results.append(self.ingest_file(copied, original_name=path.name))
        return results


def _file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()
