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
    upload_payload = upload_response.json()
    assert upload_payload["task_id"]
    assert upload_payload["status"] in {"pending", "succeeded"}
    assert upload_payload["version"] >= 1
    document_id = upload_payload["document_id"]

    documents = client.get("/api/documents", headers=headers).json()["documents"]
    indexed = next(item for item in documents if item["document_id"] == document_id)
    assert indexed["status"] == "succeeded"
    assert indexed["chunk_count"] > 0

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


def test_upload_deduplicates_by_file_hash_and_exposes_chunk_metadata() -> None:
    headers = auth_headers()
    name = f"duplicate-{uuid.uuid4().hex[:8]}.txt"
    content = b"# Hash Policy\n\nThe same file should not be indexed twice."
    first = client.post(
        "/api/documents/upload",
        files={"file": (name, content, "text/plain")},
        headers=headers,
    )
    assert first.status_code == 200
    first_payload = first.json()

    second = client.post(
        "/api/documents/upload",
        files={"file": (name, content, "text/plain")},
        headers=headers,
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["duplicate"] is True
    assert second_payload["document_id"] == first_payload["document_id"]

    chunks = client.get(
        f"/api/documents/{first_payload['document_id']}/chunks",
        headers=headers,
    ).json()["chunks"]
    assert chunks
    metadata = chunks[0]["metadata"]
    assert chunks[0]["hash"]
    assert "title_path" in chunks[0]
    assert "block_type" in chunks[0]
    assert metadata["hash"] == chunks[0]["hash"]
    assert "source_page" in metadata


def test_conversation_lifecycle() -> None:
    headers = auth_headers()
    question = f"会话生命周期测试 {uuid.uuid4().hex[:8]}"
    ask_response = client.post(
        "/api/chat/ask",
        json={"question": question},
        headers=headers,
    )
    assert ask_response.status_code == 200
    conversation_id = ask_response.json()["conversation_id"]

    list_response = client.get("/api/chat/conversations", headers=headers)
    assert list_response.status_code == 200
    conversations = list_response.json()["conversations"]
    assert any(item["conversation_id"] == conversation_id for item in conversations)

    search_response = client.get(
        "/api/chat/conversations/search",
        params={"q": question[:8]},
        headers=headers,
    )
    assert search_response.status_code == 200
    assert any(
        item["conversation_id"] == conversation_id
        for item in search_response.json()["conversations"]
    )

    detail_response = client.get(
        f"/api/chat/conversations/{conversation_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    messages = detail_response.json()["messages"]
    assert messages[0]["question"] == question
    assert "sources" in messages[0]

    rename_response = client.patch(
        f"/api/chat/conversations/{conversation_id}",
        json={"title": "已重命名会话", "pinned": True},
        headers=headers,
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["title"] == "已重命名会话"
    assert rename_response.json()["pinned"] is True

    delete_response = client.delete(
        f"/api/chat/conversations/{conversation_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True
    assert client.get(
        f"/api/chat/conversations/{conversation_id}",
        headers=headers,
    ).status_code == 404


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
