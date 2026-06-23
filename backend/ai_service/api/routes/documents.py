import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.ai_service.api.dependencies import knowledge_service, vector_store
from backend.ai_service.core.config import DATA_DIR
from backend.ai_service.security.dependencies import require_permission
from backend.ai_service.security.models import User


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(require_permission("document:upload")),
) -> dict:
    try:
        result = await knowledge_service.ingest_upload(file, tenant_id=user.tenant_id)
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
def list_documents(user: User = Depends(require_permission("document:list"))) -> dict:
    return {"documents": vector_store.list_documents(tenant_id=user.tenant_id)}


@router.delete("/api/documents/{document_id}")
def delete_document(document_id: str, user: User = Depends(require_permission("document:delete"))) -> dict:
    deleted_chunks = vector_store.delete_document(document_id, tenant_id=user.tenant_id)
    if deleted_chunks == 0:
        raise HTTPException(status_code=404, detail="document not found")
    return {"document_id": document_id, "deleted_chunks": deleted_chunks}


@router.post("/api/documents/batch-delete")
def batch_delete_documents(body: dict, user: User = Depends(require_permission("document:batch_delete"))) -> dict:
    document_ids = body.get("document_ids")
    if not isinstance(document_ids, list) or not document_ids:
        raise HTTPException(
            status_code=400,
            detail="document_ids must be a non-empty list",
        )
    deleted_chunks = vector_store.delete_documents(document_ids, tenant_id=user.tenant_id)
    if deleted_chunks == 0:
        raise HTTPException(status_code=404, detail="no documents found")
    return {"document_ids": document_ids, "deleted_chunks": deleted_chunks}


@router.get("/api/documents/{document_id}/chunks")
def list_document_chunks(document_id: str, user: User = Depends(require_permission("document:read"))) -> dict:
    return {
        "document_id": document_id,
        "chunks": vector_store.list_document_chunks(document_id, tenant_id=user.tenant_id),
    }


@router.post("/api/knowledge/rebuild")
def rebuild_from_uploads(user: User = Depends(require_permission("knowledge:rebuild"))) -> dict:
    vector_store.clear(tenant_id=user.tenant_id)
    directory = Path(DATA_DIR) / "uploads" / user.tenant_id
    results = knowledge_service.ingest_directory(directory, tenant_id=user.tenant_id)
    return {"message": "knowledge base rebuilt", "documents": results}
