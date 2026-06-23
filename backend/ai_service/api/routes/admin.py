from fastapi import APIRouter, Depends, HTTPException

from backend.ai_service.api.schemas import CreateTenantRequest, CreateUserRequest
from backend.ai_service.security.dependencies import require_permission, user_service
from backend.ai_service.security.models import User


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/tenants", status_code=201)
def create_tenant(
    request: CreateTenantRequest,
    actor: User = Depends(require_permission("user:manage")),
) -> dict:
    if not actor.is_platform_admin:
        raise HTTPException(status_code=403, detail="只有平台管理员可以创建租户")
    try:
        return user_service.create_tenant(request.name, request.slug)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/users", status_code=201)
def create_user(
    request: CreateUserRequest,
    actor: User = Depends(require_permission("user:manage")),
) -> dict:
    tenant_id = request.tenant_id or actor.tenant_id
    if tenant_id != actor.tenant_id and not actor.is_platform_admin:
        raise HTTPException(status_code=403, detail="不能在其他租户中创建用户")
    try:
        user = user_service.create_user(
            email=request.email, name=request.name, password=request.password,
            role=request.role, tenant_id=tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return user.to_public_dict()
