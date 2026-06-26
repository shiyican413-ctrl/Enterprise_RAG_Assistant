from pathlib import Path
import uuid

from fastapi.testclient import TestClient

from backend.ai_service.main import app


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "Admin123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_and_ask() -> None:
    headers = auth_headers()
    sample = Path("data/sample_policy.txt")
    with sample.open("rb") as file:
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("sample_policy.txt", file, "text/plain")},
            headers=headers,
        )
    assert upload_response.status_code == 200
    assert upload_response.json()["chunk_count"] > 0

    ask_response = client.post(
        "/api/chat/ask",
        json={"question": "When are reimbursements paid?"},
        headers=headers,
    )
    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert payload["answer"]
    assert payload["sources"]
    assert payload["trace_id"]
    assert [step["step"] for step in payload["route"]][:3] == [
        "guardrails.input",
        "memory.load",
        "planner.create_plan",
    ]


def test_sensitive_api_requires_login() -> None:
    assert client.get("/api/documents").status_code == 401
    assert client.post("/api/chat/ask", json={"question": "hello"}).status_code == 401


def test_auth_me() -> None:
    response = client.get("/api/auth/me", headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_only_admin_can_mutate_knowledge_base() -> None:
    admin_headers = auth_headers()
    suffix = uuid.uuid4().hex[:8]
    email = f"maintainer-{suffix}@example.com"
    user_response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "email": email,
            "name": "知识库维护员",
            "password": "Maintainer123!",
            "role": "maintainer",
        },
    )
    assert user_response.status_code == 201

    login_response = client.post(
        "/api/auth/login", json={"email": email, "password": "Maintainer123!"}
    )
    assert login_response.status_code == 200
    maintainer_headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    assert client.get("/api/documents", headers=maintainer_headers).status_code == 200
    assert client.get(
        "/api/documents/missing-document/chunks", headers=maintainer_headers
    ).status_code == 200
    assert client.post(
        "/api/documents/upload",
        headers=maintainer_headers,
        files={"file": ("sample.txt", b"hello", "text/plain")},
    ).status_code == 403
    assert client.delete(
        "/api/documents/missing-document", headers=maintainer_headers
    ).status_code == 403
    assert client.post(
        "/api/documents/batch-delete",
        headers=maintainer_headers,
        json={"document_ids": ["missing-document"]},
    ).status_code == 403
    assert client.post(
        "/api/knowledge/rebuild", headers=maintainer_headers
    ).status_code == 403


def test_tenant_document_isolation() -> None:
    platform_headers = auth_headers()
    suffix = uuid.uuid4().hex[:8]
    tenant_response = client.post(
        "/api/admin/tenants",
        headers=platform_headers,
        json={"name": f"测试租户 {suffix}", "slug": f"tenant-{suffix}"},
    )
    assert tenant_response.status_code == 201
    tenant_id = tenant_response.json()["id"]

    email = f"admin-{suffix}@example.com"
    user_response = client.post(
        "/api/admin/users",
        headers=platform_headers,
        json={
            "email": email, "name": "租户管理员", "password": "Tenant123!",
            "role": "admin", "tenant_id": tenant_id,
        },
    )
    assert user_response.status_code == 201
    assert user_response.json()["tenant_id"] == tenant_id

    login_response = client.post(
        "/api/auth/login", json={"email": email, "password": "Tenant123!"}
    )
    tenant_headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }
    content = f"tenant-private-{suffix}".encode()
    upload = client.post(
        "/api/documents/upload", headers=tenant_headers,
        files={"file": (f"{suffix}.txt", content, "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    tenant_documents = client.get("/api/documents", headers=tenant_headers).json()["documents"]
    platform_documents = client.get("/api/documents", headers=platform_headers).json()["documents"]
    assert any(item["document_id"] == document_id for item in tenant_documents)
    assert all(item["document_id"] != document_id for item in platform_documents)
    assert client.get(
        f"/api/documents/{document_id}/chunks", headers=platform_headers
    ).json()["chunks"] == []
