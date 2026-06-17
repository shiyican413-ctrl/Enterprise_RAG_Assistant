from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from backend.ai_service.services.agent_service import (
    AgentRun,
    AgentStep,
    AgentTool,
    ReActAgent,
)
from backend.ai_service.services.chat_model_service import AnswerMode, DoubaoChatClient
from backend.ai_service.services.planner_service import Plan
from backend.ai_service.services.trace_service import TraceContext, TraceService, traced_step
from backend.ai_service.services.vector_store_service import SearchResult
from backend.ai_service.tools.base import ToolContext
from backend.ai_service.tools.registry import ToolRegistry


@dataclass
class ExecutionResult:
    answer: str
    sources: list[dict]
    model: str | None
    raw_results: list[SearchResult] = field(default_factory=list)
    agent_steps: list[dict[str, Any]] = field(default_factory=list)


class ExecutorService:
    def __init__(
        self,
        *,
        tool_registry: ToolRegistry,
        chat_client: DoubaoChatClient,
        trace_service: TraceService | None = None,
    ) -> None:
        self.tool_registry = tool_registry
        self.chat_client = chat_client
        self.trace_service = trace_service or TraceService()

    def execute(
        self,
        *,
        plan: Plan,
        trace: TraceContext,
        top_k: int,
    ) -> ExecutionResult:
        tool_context = ToolContext(trace_id=trace.trace_id, top_k=top_k)
        agent_run = AgentRun(answer="", sources=[], model=None, steps=[], raw_results=[])

        if _has_step(plan, "agent_answer"):
            agent_run = self._run_agent(
                question=plan.question,
                answer_mode=plan.answer_mode,
                tool_context=tool_context,
                trace=trace,
            )

        results = agent_run.raw_results
        sources = agent_run.sources
        answer = agent_run.answer
        model = agent_run.model

        if not sources and _has_step(plan, "knowledge_search"):
            with traced_step(self.trace_service, trace, "tool.knowledge_search"):
                search_result = self.tool_registry.run(
                    "knowledge_search",
                    {"query": plan.question},
                    tool_context,
                )
            results = search_result.raw_results
            sources = search_result.sources

        if not answer and _has_step(plan, "answer_generation"):
            with traced_step(self.trace_service, trace, "model.answer"):
                answer, model = self.build_answer(
                    question=plan.question,
                    results=results,
                    answer_mode=plan.answer_mode,
                )

        if not answer:
            answer = build_template_answer(plan.question, results)

        return ExecutionResult(
            answer=answer,
            sources=sources,
            model=model,
            raw_results=results,
            agent_steps=_agent_steps_payload(agent_run),
        )

    async def stream_execute(
        self,
        *,
        plan: Plan,
        trace: TraceContext,
        top_k: int,
    ) -> AsyncIterator[dict]:
        tool_context = ToolContext(trace_id=trace.trace_id, top_k=top_k)
        agent_run = AgentRun(answer="", sources=[], model=None, steps=[], raw_results=[])
        results: list[SearchResult] = []
        sources: list[dict] = []
        answer = ""
        model: str | None = None

        if _has_step(plan, "agent_answer"):
            yield {
                "type": "phase",
                "layer": "agent",
                "status": "start",
                "label": "执行层 · 智能体推理与检索",
            }
            try:
                with traced_step(self.trace_service, trace, "agent.answer"):
                    for item in self._run_agent_stream(
                        question=plan.question,
                        answer_mode=plan.answer_mode,
                        tool_context=tool_context,
                    ):
                        if item.get("type") == "thought":
                            yield {
                                "type": "agent_step",
                                "content": _agent_step_payload(item["step"]),
                            }
                        elif item.get("type") == "final":
                            agent_run = item["run"]
            except Exception:
                agent_run = AgentRun(
                    answer="", sources=[], model=None, steps=[], raw_results=[]
                )
            yield _route_step_event(self.trace_service, trace)
            yield {
                "type": "phase",
                "layer": "agent",
                "status": "done",
                "label": "执行层 · 智能体推理与检索",
            }

            results = agent_run.raw_results
            sources = agent_run.sources
            answer = agent_run.answer
            model = agent_run.model

        if not sources and _has_step(plan, "knowledge_search"):
            with traced_step(self.trace_service, trace, "tool.knowledge_search"):
                search_result = self.tool_registry.run(
                    "knowledge_search",
                    {"query": plan.question},
                    tool_context,
                )
            results = search_result.raw_results
            sources = search_result.sources
            yield _route_step_event(self.trace_service, trace)

        # Command layer: produce and stream the final answer (single phase
        # wrapping reuse-of-agent-answer, streamed generation, and fallback).
        yield {
            "type": "phase",
            "layer": "answer",
            "status": "start",
            "label": "命令层 · 生成最终回答",
        }
        answer_parts: list[str] = []

        if answer:
            for chunk in chunk_text(answer):
                answer_parts.append(chunk)
                yield {"type": "answer_delta", "content": chunk}
        elif results and self.chat_client.enabled and _has_step(plan, "answer_generation"):
            try:
                with traced_step(self.trace_service, trace, "model.answer"):
                    async for delta in self.chat_client.stream_complete(
                        messages=build_messages(plan.question, results, plan.answer_mode),
                        mode=plan.answer_mode,
                        temperature=0.1 if plan.answer_mode == "thinking" else 0.2,
                    ):
                        model = delta.model
                        answer_parts.append(delta.content)
                        yield {"type": "answer_delta", "content": delta.content}
                yield _route_step_event(self.trace_service, trace)
            except Exception as exc:
                fallback = build_template_answer(plan.question, results)
                if answer_parts:
                    fallback = (
                        "\n\nModel streaming stopped early; partial output was kept. "
                        f"Error: {exc}"
                    )
                else:
                    fallback = (
                        f"{fallback}\n\n"
                        f"Model generation is unavailable, so a local fallback was used. Error: {exc}"
                    )
                for chunk in chunk_text(fallback):
                    answer_parts.append(chunk)
                    yield {"type": "answer_delta", "content": chunk}

        if not answer_parts:
            fallback = build_template_answer(plan.question, results)
            for chunk in chunk_text(fallback):
                answer_parts.append(chunk)
                yield {"type": "answer_delta", "content": chunk}

        yield {
            "type": "phase",
            "layer": "answer",
            "status": "done",
            "label": "命令层 · 生成最终回答",
        }

        yield {
            "type": "executor_result",
            "answer": "".join(answer_parts),
            "sources": sources,
            "model": model,
        }

    def _run_agent(
        self,
        *,
        question: str,
        answer_mode: AnswerMode,
        tool_context: ToolContext,
        trace: TraceContext,
    ) -> AgentRun:
        tools = [
            AgentTool(
                name=tool["name"],
                description=tool["description"],
                run=lambda payload, name=tool["name"]: self.tool_registry.run(
                    name,
                    payload,
                    tool_context,
                ),
            )
            for tool in self.tool_registry.descriptions()
        ]
        agent = ReActAgent(chat_client=self.chat_client, tools=tools)
        try:
            with traced_step(self.trace_service, trace, "agent.answer"):
                return agent.run(question=question, answer_mode=answer_mode)
        except Exception:
            return AgentRun(answer="", sources=[], model=None, steps=[], raw_results=[])

    def _run_agent_stream(
        self,
        *,
        question: str,
        answer_mode: AnswerMode,
        tool_context: ToolContext,
    ):
        tools = [
            AgentTool(
                name=tool["name"],
                description=tool["description"],
                run=lambda payload, name=tool["name"]: self.tool_registry.run(
                    name,
                    payload,
                    tool_context,
                ),
            )
            for tool in self.tool_registry.descriptions()
        ]
        agent = ReActAgent(chat_client=self.chat_client, tools=tools)
        yield from agent.run_stream(question=question, answer_mode=answer_mode)

    def build_answer(
        self,
        *,
        question: str,
        results: list[SearchResult],
        answer_mode: AnswerMode,
    ) -> tuple[str, str | None]:
        if not results:
            return build_template_answer(question, results), None

        if self.chat_client.enabled:
            try:
                response = self.chat_client.complete(
                    messages=build_messages(question, results, answer_mode),
                    mode=answer_mode,
                    temperature=0.1 if answer_mode == "thinking" else 0.2,
                )
                return response.content, response.model
            except Exception as exc:
                fallback = build_template_answer(question, results)
                return (
                    f"{fallback}\n\n"
                    f"Model generation is unavailable, so a local fallback was used. Error: {exc}",
                    None,
                )

        return build_template_answer(question, results), None


def build_template_answer(question: str, results: list[SearchResult]) -> str:
    if not results:
        return (
            "I could not find enough relevant content in the current knowledge base. "
            "Please upload enterprise policies, product manuals, or FAQ documents, then ask again."
        )

    evidence = "\n".join(
        f"{index}. {result.chunk.content[:260]}"
        for index, result in enumerate(results[:3], start=1)
    )
    return (
        f"Based on the most relevant knowledge base content, here is what I found for "
        f"'{question}':\n\n{evidence}\n\n"
        "This answer was summarized from retrieved knowledge chunks."
    )


def chunk_text(text: str, size: int = 48) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


def build_messages(
    question: str,
    results: list[SearchResult],
    answer_mode: AnswerMode,
) -> list[dict[str, str]]:
    evidence = "\n\n".join(
        (
            f"[{index}] Source: {result.chunk.document_name}, "
            f"chunk: {result.chunk.chunk_index}\n"
            f"{result.chunk.content[:1200]}"
        )
        for index, result in enumerate(results, start=1)
    )
    mode_instruction = (
        "Give a concise answer in 3 to 6 bullet points."
        if answer_mode == "fast"
        else "Analyze the evidence carefully, then provide only the final structured answer."
    )
    return [
        {
            "role": "system",
            "content": (
                "You are an enterprise RAG assistant. Answer strictly from the provided "
                "evidence. Do not invent facts outside the evidence. Cite key claims "
                "with references such as [1] or [2]. If evidence is insufficient, say so clearly."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Answer mode: {answer_mode}\n"
                f"Answer requirement: {mode_instruction}\n\n"
                f"User question: {question}\n\n"
                f"Available evidence:\n{evidence}"
            ),
        },
    ]


def _agent_step_payload(step: AgentStep) -> dict[str, Any]:
    return {
        "thought": step.thought,
        "action": step.action,
        "action_input": step.action_input,
        "observation": step.observation,
    }


def _agent_steps_payload(agent_run: AgentRun) -> list[dict[str, Any]]:
    return [_agent_step_payload(step) for step in agent_run.steps]


def _route_step_event(trace_service: TraceService, trace: TraceContext) -> dict:
    return {"type": "route_step", "step": trace_service.latest_route_step(trace)}


def _has_step(plan: Plan, step_type: str) -> bool:
    return any(step.step_type == step_type for step in plan.steps)
