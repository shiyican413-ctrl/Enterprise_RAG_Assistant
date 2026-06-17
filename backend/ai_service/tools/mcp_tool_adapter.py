from collections.abc import Callable

from backend.ai_service.tools.base import ToolContext, ToolResult


class MCPToolAdapter:
    """Adapter seam for future MCP server tools."""

    def __init__(
        self,
        name: str,
        description: str,
        runner: Callable[[dict, ToolContext], ToolResult],
    ) -> None:
        self.name = name
        self.description = description
        self._runner = runner

    def run(self, payload: dict, context: ToolContext) -> ToolResult:
        return self._runner(payload, context)
