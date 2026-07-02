import asyncio
from collections.abc import AsyncIterator

from backend.ai_service.core.config import TOP_K
from backend.ai_service.llm.chat_client import AnswerMode
from backend.ai_service.agent.executor import ExecutorService
from backend.ai_service.agent.guardrails import GuardrailService
from backend.ai_service.application.memory import MemoryService
from backend.ai_service.agent.planner import PlannerService
from backend.ai_service.observability.tracing import TraceContext, TraceService, traced_step


class ChatWorkflow:
    """Fixed application state flow; no model calls live in this layer."""

    def __init__(
        self,
        *,
        memory: MemoryService,
        planner: PlannerService,
        executor: ExecutorService,
        trace_service: TraceService,
        guardrails: GuardrailService | None = None,
    ) -> None:
        self.memory = memory
        self.planner = planner
        self.executor = executor
        self.trace_service = trace_service
        self.guardrails = guardrails or GuardrailService()

    def run_chat(
        self,
        *,
        trace: TraceContext,
        question: str,
        conversation_id: str | None = None,
        top_k: int = TOP_K,
        answer_mode: AnswerMode = "fast",
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        with traced_step(self.trace_service, trace, "guardrails.input"):
            guardrail = self.guardrails.validate_chat_input(question)
        if not guardrail.allowed:
            raise ValueError(guardrail.reason)

        with traced_step(self.trace_service, trace, "memory.load"):
            memory_context = self.memory.load_context(
                conversation_id, user_id=user_id, tenant_id=tenant_id
            )
            if conversation_id and user_id and not memory_context:
                raise ValueError("会话不存在或无权访问")

        with traced_step(self.trace_service, trace, "planner.create_plan"):
            plan = self.planner.create_plan(
                question=question,
                answer_mode=answer_mode,
                memory=memory_context,
            )

        execution = self.executor.execute(
            plan=plan,
            trace=trace,
            top_k=top_k,
            tenant_id=tenant_id,
            memory=memory_context,
        )
        route = self.trace_service.route(trace)

        with traced_step(self.trace_service, trace, "memory.append_turn"):
            turn = self.memory.append_turn(
                question=question,
                answer=execution.answer,
                sources=execution.sources,
                conversation_id=conversation_id,
                user_id=user_id,
                tenant_id=tenant_id,
                model=execution.model,
                answer_mode=answer_mode,
                trace_id=trace.trace_id,
                route=route,
                agent_steps=execution.agent_steps,
            )

        final_route = self.trace_service.route(trace)
        return {
            "conversation_id": turn["conversation_id"],
            "trace_id": trace.trace_id,
            "answer": execution.answer,
            "sources": execution.sources,
            "answer_mode": answer_mode,
            "model": execution.model,
            "agent_steps": execution.agent_steps,
            "route": final_route,
        }

    async def stream_chat(
        self,
        *,
        trace: TraceContext,
        question: str,
        conversation_id: str | None = None,
        top_k: int = TOP_K,
        answer_mode: AnswerMode = "fast",
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> AsyncIterator[dict]:
        def route_step() -> dict:
            return {"type": "route_step", "step": self.trace_service.latest_route_step(trace)}

        yield {"type": "phase", "layer": "guardrails", "status": "start", "label": "输入安全校验"}
        with traced_step(self.trace_service, trace, "guardrails.input"):
            guardrail = self.guardrails.validate_chat_input(question)
        if not guardrail.allowed:
            raise ValueError(guardrail.reason)
        yield route_step()
        yield {"type": "phase", "layer": "guardrails", "status": "done", "label": "输入安全校验"}

        yield {"type": "phase", "layer": "memory", "status": "start", "label": "加载会话记忆"}
        with traced_step(self.trace_service, trace, "memory.load"):
            memory_context = self.memory.load_context(
                conversation_id, user_id=user_id, tenant_id=tenant_id
            )
            if conversation_id and user_id and not memory_context:
                raise ValueError("会话不存在或无权访问")
        yield route_step()
        yield {"type": "phase", "layer": "memory", "status": "done", "label": "加载会话记忆"}

        yield {"type": "phase", "layer": "planner", "status": "start", "label": "规划层 · 分析问题并制定路线"}
        with traced_step(self.trace_service, trace, "planner.create_plan"):
            plan = await asyncio.to_thread(
                self.planner.create_plan,
                question=question,
                answer_mode=answer_mode,
                memory=memory_context,
            )
        yield route_step()
        yield {
            "type": "plan",
            "strategy": plan.strategy,
            "rationale": plan.rationale,
            "steps": [{"name": step.name, "step_type": step.step_type} for step in plan.steps],
        }
        yield {"type": "phase", "layer": "planner", "status": "done", "label": "规划层 · 分析问题并制定路线"}

        execution_result: dict | None = None
        async for event in self.executor.stream_execute(
            plan=plan,
            trace=trace,
            top_k=top_k,
            tenant_id=tenant_id,
            memory=memory_context,
        ):
            if event.get("type") == "executor_result":
                execution_result = event
                continue
            yield event

        execution_result = execution_result or {
            "answer": "",
            "sources": [],
            "model": None,
        }
        route = self.trace_service.route(trace)

        with traced_step(self.trace_service, trace, "memory.append_turn"):
            turn = self.memory.append_turn(
                question=question,
                answer=str(execution_result.get("answer") or ""),
                sources=list(execution_result.get("sources") or []),
                conversation_id=conversation_id,
                user_id=user_id,
                tenant_id=tenant_id,
                model=execution_result.get("model"),
                answer_mode=answer_mode,
                trace_id=trace.trace_id,
                route=route,
                agent_steps=list(execution_result.get("agent_steps") or []),
            )
        yield route_step()
        final_route = self.trace_service.route(trace)

        yield {"type": "sources", "content": execution_result.get("sources") or []}
        yield {
            "type": "done",
            "conversation_id": turn["conversation_id"],
            "trace_id": trace.trace_id,
            "answer_mode": answer_mode,
            "model": execution_result.get("model"),
            "route": final_route,
        }
