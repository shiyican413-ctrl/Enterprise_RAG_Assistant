from fastapi import APIRouter

from backend.ai_service.api.routes import admin, auth, chat, documents, health


router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(admin.router)
router.include_router(documents.router)
router.include_router(chat.router)
