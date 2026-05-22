from pathlib import Path

from fastapi.testclient import TestClient

from backend.ai_service.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_and_ask() -> None:
    sample = Path("data/sample_policy.txt")
    with sample.open("rb") as file:
        upload_response = client.post(
            "/api/documents/upload",
            files={"file": ("sample_policy.txt", file, "text/plain")},
        )
    assert upload_response.status_code == 200
    assert upload_response.json()["chunk_count"] > 0

    ask_response = client.post(
        "/api/chat/ask",
        json={"question": "报销多久可以打款？"},
    )
    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert payload["answer"]
    assert payload["sources"]
