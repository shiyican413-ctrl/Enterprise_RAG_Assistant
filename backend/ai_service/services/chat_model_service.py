import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal

import httpx

from backend.ai_service.config import (
    CHAT_TIMEOUT_SECONDS,
    GLM_API_KEY,
    GLM_CHAT_URL,
    GLM_FAST_MODEL,
    GLM_THINKING_MODEL,
)


AnswerMode = Literal["fast", "thinking"]


@dataclass(frozen=True)
class ChatModelResponse:
    content: str
    reasoning_content: str | None
    model: str


@dataclass(frozen=True)
class ChatModelDelta:
    content: str
    model: str


class GLMChatClient:
    def __init__(
        self,
        api_key: str = GLM_API_KEY,
        url: str = GLM_CHAT_URL,
        fast_model: str = GLM_FAST_MODEL,
        thinking_model: str = GLM_THINKING_MODEL,
        timeout_seconds: float = CHAT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key
        self.url = url
        self.fast_model = fast_model
        self.thinking_model = thinking_model
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def model_for_mode(self, mode: AnswerMode) -> str:
        if mode == "thinking":
            return self.thinking_model
        return self.fast_model

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        mode: AnswerMode,
        temperature: float = 0.2,
    ) -> ChatModelResponse:
        if not self.enabled:
            raise RuntimeError("GLM_API_KEY is not configured")

        model = self.model_for_mode(mode)
        payload = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.url, headers=headers, json=payload)
            response.raise_for_status()

        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("Invalid chat response from GLM")

        message = choices[0].get("message") or {}
        content = _normalize_text(message.get("content"))
        reasoning_content = _normalize_text(message.get("reasoning_content"))
        if not content:
            raise RuntimeError("Empty chat response from GLM")

        return ChatModelResponse(
            content=content,
            reasoning_content=reasoning_content or None,
            model=model,
        )

    async def stream_complete(
        self,
        messages: Sequence[dict[str, str]],
        mode: AnswerMode,
        temperature: float = 0.2,
    ) -> AsyncIterator[ChatModelDelta]:
        if not self.enabled:
            raise RuntimeError("GLM_API_KEY is not configured")

        model = self.model_for_mode(mode)
        payload = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream(
                "POST",
                self.url,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    data = _stream_data(line)
                    if not data:
                        continue
                    if data == "[DONE]":
                        break

                    try:
                        body = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choices = body.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = _normalize_delta_text(delta.get("content"))
                    if content:
                        yield ChatModelDelta(content=content, model=model)


def _normalize_text(value: object) -> str:
    text = ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        text = "\n".join(part.strip() for part in parts if part.strip())
    return _strip_model_markers(text.strip())


def _normalize_delta_text(value: object) -> str:
    if isinstance(value, str):
        return _strip_model_markers(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return _strip_model_markers("".join(parts))
    return ""


def _stream_data(line: str) -> str:
    line = line.strip()
    if not line or line.startswith(":"):
        return ""
    if line.startswith("data:"):
        return line.removeprefix("data:").strip()
    return line


def _strip_model_markers(text: str) -> str:
    markers = (
        "<|begin_of_box|>",
        "<|end_of_box|>",
        "<|begin_of_thought|>",
        "<|end_of_thought|>",
    )
    for marker in markers:
        text = text.replace(marker, "")
    return text.strip()
