import json

import httpx

from backend.ai_service.llm.chat_client import BailianChatClient
def test_mode_payloads(monkeypatch):
    payloads: list[dict] = []
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "answer"}}]},
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    client = BailianChatClient(
        api_key="test-key",
        fast_model="qwen3.5-flash",
        thinking_model="qwen3.7-plus",
        thinking_budget=4096,
    )

    client.complete([{"role": "user", "content": "hello"}], "fast")
    client.complete([{"role": "user", "content": "analyze"}], "thinking")

    assert payloads[0]["model"] == "qwen3.5-flash"
    assert payloads[0]["enable_thinking"] is False
    assert "thinking_budget" not in payloads[0]
    assert payloads[1]["model"] == "qwen3.7-plus"
    assert payloads[1]["enable_thinking"] is True
    assert payloads[1]["thinking_budget"] == 4096
