import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class TraceStep:
    name: str
    status: str = "ok"
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    duration_ms: float | None = None


@dataclass
class TraceContext:
    trace_id: str
    started_at: str
    steps: list[TraceStep] = field(default_factory=list)


class TraceService:
    def start_trace(self) -> TraceContext:
        return TraceContext(
            trace_id=str(uuid.uuid4()),
            started_at=datetime.now(UTC).isoformat(),
        )

    def add_step(
        self,
        trace: TraceContext,
        name: str,
        *,
        status: str = "ok",
        input: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        trace.steps.append(
            TraceStep(
                name=name,
                status=status,
                input=input,
                output=output,
                error=error,
                duration_ms=duration_ms,
            )
        )

    def route(self, trace: TraceContext) -> list[dict[str, Any]]:
        return [
            {
                "step": step.name,
                "status": step.status,
                "duration_ms": step.duration_ms,
                "error": step.error,
            }
            for step in trace.steps
        ]

    def latest_route_step(self, trace: TraceContext) -> dict[str, Any] | None:
        """Return the most recently recorded step as a route dict, or None."""
        steps = self.route(trace)
        return steps[-1] if steps else None


class traced_step:
    def __init__(self, trace_service: TraceService, trace: TraceContext, name: str) -> None:
        self.trace_service = trace_service
        self.trace = trace
        self.name = name
        self.started = 0.0

    def __enter__(self) -> "traced_step":
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, _tb) -> bool:
        duration_ms = round((time.perf_counter() - self.started) * 1000, 2)
        if exc is None:
            self.trace_service.add_step(
                self.trace,
                self.name,
                status="ok",
                duration_ms=duration_ms,
            )
            return False

        self.trace_service.add_step(
            self.trace,
            self.name,
            status="error",
            error=str(exc),
            duration_ms=duration_ms,
        )
        return False
