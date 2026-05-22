from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.ai_service.api.routes import router
from backend.ai_service.config import APP_NAME, APP_VERSION


app = FastAPI(title=APP_NAME, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
