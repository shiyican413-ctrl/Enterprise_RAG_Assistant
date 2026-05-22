from collections.abc import Sequence

import httpx

from backend.ai_service.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_TIMEOUT_SECONDS,
    GLM_API_KEY,
    GLM_EMBEDDING_MODEL,
    GLM_EMBEDDING_URL,
)


class GLMEmbeddingClient:
    def __init__(
        self,
        api_key: str = GLM_API_KEY,
        model: str = GLM_EMBEDDING_MODEL,
        url: str = GLM_EMBEDDING_URL,
        batch_size: int = EMBEDDING_BATCH_SIZE,
        timeout_seconds: float = EMBEDDING_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.url = url
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [text for text in texts if text.strip()]
        if not cleaned:
            return []
        if not self.enabled:
            raise RuntimeError("GLM_API_KEY is not configured")

        embeddings: list[list[float]] = []
        for start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[start : start + self.batch_size]
            embeddings.extend(self._embed_batch(batch))
        return embeddings

    def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": list(texts),
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.url, headers=headers, json=payload)
            response.raise_for_status()

        body = response.json()
        data = sorted(body.get("data", []), key=lambda item: item.get("index", 0))
        vectors = [item.get("embedding") for item in data]
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise RuntimeError("Invalid embedding response from GLM")
        return vectors
