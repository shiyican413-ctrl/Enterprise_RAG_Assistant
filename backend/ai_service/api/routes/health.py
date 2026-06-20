from fastapi import APIRouter

from backend.ai_service.core.config import APP_VERSION, DATA_DIR


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "data_dir": str(DATA_DIR),
    }
