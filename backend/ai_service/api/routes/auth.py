from fastapi import APIRouter, Depends, HTTPException

from backend.ai_service.api.schemas import LoginRequest
from backend.ai_service.security.dependencies import get_current_user, user_service
from backend.ai_service.security.jwt_service import create_access_token
from backend.ai_service.security.models import User


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(request: LoginRequest) -> dict:
    user = user_service.authenticate(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    token, expires_in = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "user": user.to_public_dict()}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return user.to_public_dict()


@router.post("/logout", status_code=204)
def logout() -> None:
    return None
