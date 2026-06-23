from collections.abc import Callable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.ai_service.security.jwt_service import decode_access_token
from backend.ai_service.security.models import User
from backend.ai_service.security.permissions import has_permission
from backend.ai_service.security.user_service import UserService


bearer = HTTPBearer(auto_error=False)
user_service = UserService()


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="请先登录", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录") from exc
    user = user_service.get_by_id(str(claims["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已被停用")
    return user


def require_permission(permission: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=403, detail="当前账号无权执行此操作")
        return user
    return dependency
