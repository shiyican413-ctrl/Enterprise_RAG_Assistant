import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.ai_service.api.dependencies import history_service, orchestrator_service
from backend.ai_service.api.schemas import AskRequest, AskResponse
from backend.ai_service.security.dependencies import require_permission
from backend.ai_service.security.models import User


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/chat/ask", response_model=AskResponse)
def ask(request: AskRequest, user: User = Depends(require_permission("chat:ask"))) -> dict:
    return orchestrator_service.handle_chat(
        question=request.question,
        conversation_id=request.conversation_id,
        top_k=request.top_k,
        answer_mode=request.answer_mode,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )


@router.post("/api/chat/stream")
async def stream(request: AskRequest, user: User = Depends(require_permission("chat:ask"))) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        try:
            async for event in orchestrator_service.stream_chat(
                question=request.question,
                conversation_id=request.conversation_id,
                top_k=request.top_k,
                answer_mode=request.answer_mode,
                user_id=user.id,
                tenant_id=user.tenant_id,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except ValueError as exc:
            yield (
                "data: "
                f"{json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}"
                "\n\n"
            )
        except Exception:
            logger.exception("Stream error")
            yield (
                "data: "
                f"{json.dumps({'type': 'error', 'message': '服务内部错误，请稍后重试'}, ensure_ascii=False)}"
                "\n\n"
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/chat/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    user: User = Depends(require_permission("chat:read_own")),
) -> dict:
    messages = history_service.get_conversation(
        conversation_id,
        user_id=None if user.role == "admin" else user.id,
        tenant_id=user.tenant_id,
    )
    if not messages:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return {
        "conversation_id": conversation_id,
        "messages": messages,
    }
