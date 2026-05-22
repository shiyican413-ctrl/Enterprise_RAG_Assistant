import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.ai_service.api.schemas import AskRequest, AskResponse
from backend.ai_service.config import APP_VERSION, DATA_DIR
from backend.ai_service.services.knowledge_service import KnowledgeService
from backend.ai_service.services.rag_service import RAGService
from backend.ai_service.services.storage_factory import create_history_service, create_vector_store


router = APIRouter()
vector_store = create_vector_store()
knowledge_service = KnowledgeService(vector_store=vector_store)
history_service = create_history_service()
rag_service = RAGService(vector_store=vector_store, history_service=history_service)


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "data_dir": str(DATA_DIR),
    }


@router.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    try:
        result = await knowledge_service.ingest_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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


@router.post("/api/knowledge/rebuild")
def rebuild_from_uploads() -> dict:
    vector_store.clear()
    results = knowledge_service.ingest_directory(Path(DATA_DIR) / "uploads")
    return {"message": "knowledge base rebuilt", "documents": results}


@router.post("/api/chat/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict:
    return rag_service.ask(
        question=request.question,
        conversation_id=request.conversation_id,
        top_k=request.top_k,
        answer_mode=request.answer_mode,
    )


@router.post("/api/chat/stream")
async def stream(request: AskRequest) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        async for event in rag_service.stream_ask(
            question=request.question,
            conversation_id=request.conversation_id,
            top_k=request.top_k,
            answer_mode=request.answer_mode,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/api/chat/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    return {
        "conversation_id": conversation_id,
        "messages": history_service.get_conversation(conversation_id),
    }
