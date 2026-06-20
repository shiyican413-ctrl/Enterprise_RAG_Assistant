from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.ai_service.retrieval.vector_store import SearchResult


@dataclass(frozen=True)
class ToolContext:
    trace_id: str
    top_k: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    content: str
    sources: list[dict] = field(default_factory=list)
    raw_results: list[SearchResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(Protocol):
    name: str
    description: str

    def run(self, payload: dict, context: ToolContext) -> ToolResult:
        ...
