import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.ai_service.api.dependencies import knowledge_service, vector_store
from backend.ai_service.core.config import DATA_DIR


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    try:
        result = await knowledge_service.ingest_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Document ingestion failed")
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {exc}",
        ) from exc
    return {"message": "document ingested", **result}


@router.get("/api/documents")
def list_documents() -> dict:
    return {"documents": vector_store.list_documents()}


@router.delete("/api/documents/{document_id}")
def delete_document(document_id: str) -> dict:
    deleted_chunks = vector_store.delete_document(document_id)
    if deleted_chunks == 0:
        raise HTTPException(status_code=404, detail="document not found")
    return {"document_id": document_id, "deleted_chunks": deleted_chunks}


@router.post("/api/documents/batch-delete")
def batch_delete_documents(body: dict) -> dict:
    document_ids = body.get("document_ids")
    if not isinstance(document_ids, list) or not document_ids:
        raise HTTPException(
            status_code=400,
            detail="document_ids must be a non-empty list",
        )
    deleted_chunks = vector_store.delete_documents(document_ids)
    if deleted_chunks == 0:
        raise HTTPException(status_code=404, detail="no documents found")
    return {"document_ids": document_ids, "deleted_chunks": deleted_chunks}


@router.get("/api/documents/{document_id}/chunks")
def list_document_chunks(document_id: str) -> dict:
    return {
        "document_id": document_id,
        "chunks": vector_store.list_document_chunks(document_id),
    }


@router.post("/api/knowledge/rebuild")
def rebuild_from_uploads() -> dict:
    vector_store.clear()
    results = knowledge_service.ingest_directory(Path(DATA_DIR) / "uploads")
    return {"message": "knowledge base rebuilt", "documents": results}
