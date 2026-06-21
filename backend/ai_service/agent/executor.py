import asyncio
import queue as _queue_mod
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from backend.ai_service.agent.react_agent import (
    AgentRun,
    AgentStep,
    AgentTool,
    ReActAgent,
)
from backend.ai_service.core.config import (
    AGENT_MAX_STEPS,
    AGENT_RETRY_ATTEMPTS,
    AGENT_TOTAL_TIMEOUT_SECONDS,
)
from backend.ai_service.llm.chat_client import AnswerMode, DoubaoChatClient
from backend.ai_service.agent.planner import Plan
from backend.ai_service.observability.tracing import TraceContext, TraceService, traced_step
from backend.ai_service.retrieval.vector_store import SearchResult
from backend.ai_service.tools.base import ToolContext
from backend.ai_service.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Helper: run a sync generator in a thread pool so it never blocks the
# asyncio event loop.  Yields items as they become available.
# ---------------------------------------------------------------------------
_SENTINEL = object()


async def _async_iter_sync(sync_iter):
    """Wrap a synchronous iterator so it runs in a background thread."""
    q: _queue_mod.Queue[object] = _queue_mod.Queue()

    def _producer():
        try:
            for item in sync_iter:
                q.put(item)
        except Exception as exc:
            q.put(exc)
        finally:
            q.put(_SENTINEL)

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _producer)

    _get = q.get  # bound method — slightly faster in tight loop
    while True:
        item = await asyncio.to_thread(_get)
        if item is _SENTINEL:
            break
        if isinstance(item, Exception):
            raise item
        yield item


@dataclass
class ExecutionResult:
    answer: str
    sources: list[dict]
    model: str | None
    raw_results: list[SearchResult] = field(default_factory=list)
    agent_steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeConfig:
    """Deterministic Runtime knobs — owned by code, never by the LLM.

    Mirrors docs/agent改进.md §4: the Workflow/Runtime/Executor layer must
    control step budget, timeout, allowed tools and retries. Defaults come from
    environment-configured constants so behavior is identical to before unless
    an operator opts in.
    """

    max_steps: int = AGENT_MAX_STEPS
    total_timeout_seconds: float = AGENT_TOTAL_TIMEOUT_SECONDS
    retry_attempts: int = AGENT_RETRY_ATTEMPTS
    # None means "all registered tools" (backward compatible). A tuple narrows
    # what the ReAct agent is allowed to call — the "allowed_tools" control.
    allowed_tools: tuple[str, ...] | None = None


def _empty_agent_run() -> AgentRun:
    return AgentRun(answer="", sources=[], model=None, steps=[], raw_results=[])


class ExecutorService:
    """The Runtime layer.

    Despite the legacy name, this is the deterministic execution中枢 described
    in docs/agent改进.md §4: it owns step budget, timeout, allowed tools and
    retries — the things that must stay "稳" and never be delegated to the LLM.
    The LLM-driven reasoning lives in ``ReActAgent``; this class orchestrates
    and constrains it.
    """

    def __init__(
        self,
        *,
        tool_registry: ToolRegistry,
        chat_client: DoubaoChatClient,
        trace_service: TraceService | None = None,
        runtime_config: RuntimeConfig | None = None,
    ) -> None:
        self.tool_registry = tool_registry
        self.chat_client = chat_client
        self.trace_service = trace_service or TraceService()
        self.runtime_config = runtime_config or RuntimeConfig()

    def execute(
        self,
        *,
        plan: Plan,
        trace: TraceContext,
        top_k: int,
    ) -> ExecutionResult:
        tool_context = ToolContext(trace_id=trace.trace_id, top_k=top_k)
        results: list[SearchResult] = []
        sources: list[dict] = []

        # Phase 1: run knowledge_search steps in order (Route B).
        for step in plan.steps:
            if step.step_type != "knowledge_search":
                continue
            query = str(step.input.get("query") or plan.question)
            with traced_step(self.trace_service, trace, "tool.knowledge_search"):
                search_result = self.tool_registry.run(
                    "knowledge_search",
                    {"query": query},
                    tool_context,
                )
            results = search_result.raw_results
            sources = search_result.sources

        # Phase 2: run agent_answer step — unified answer generation.
        evidence = results or None
        agent_run = AgentRun(answer="", sources=[], model=None, steps=[], raw_results=[])
        for step in plan.steps:
            if step.step_type != "agent_answer":
                continue
            agent_run = self._run_agent(
                question=plan.question,
                answer_mode=plan.answer_mode,
                tool_context=tool_context,
                trace=trace,
                evidence=evidence,
            )
            break

        answer = agent_run.answer
        model = agent_run.model

        # Merge agent-sourced results when executor didn't pre-fetch any.
        if not sources:
            sources = agent_run.sources
            results = agent_run.raw_results

        # Non-LLM fallback when agent produced nothing.
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
        results: list[SearchResult] = []
        sources: list[dict] = []
        agent_run = AgentRun(answer="", sources=[], model=None, steps=[], raw_results=[])
        model: str | None = None
        has_search_step = any(s.step_type == "knowledge_search" for s in plan.steps)

        # Phase 1 (Route B only): knowledge retrieval — runs BEFORE agent.
        if has_search_step:
            yield {
                "type": "phase",
                "layer": "agent",
                "status": "start",
                "label": "执行层 · 智能体推理与检索",
            }
            for step in plan.steps:
                if step.step_type != "knowledge_search":
                    continue
                query = str(step.input.get("query") or plan.question)
                with traced_step(self.trace_service, trace, "tool.knowledge_search"):
                    search_result = await asyncio.to_thread(
                        self.tool_registry.run,
                        "knowledge_search",
                        {"query": query},
                        tool_context,
                    )
                if search_result.raw_results:
                    results.extend(search_result.raw_results)
                if search_result.sources:
                    sources.extend(search_result.sources)
                yield _route_step_event(self.trace_service, trace)

        # Phase 2: agent reasoning — always runs (Route A and Route B).
        # In Route A, open the agent phase here (no search phase preceded).
        if not has_search_step:
            yield {
                "type": "phase",
                "layer": "agent",
                "status": "start",
                "label": "执行层 · 智能体推理与检索",
            }
        evidence = results or None
        try:
            with traced_step(self.trace_service, trace, "agent.answer"):
                async for item in _async_iter_sync(
                    self._run_agent_stream(
                        question=plan.question,
                        answer_mode=plan.answer_mode,
                        tool_context=tool_context,
                        evidence=evidence,
                    )
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

        # Merge agent-sourced results when executor didn't pre-fetch any.
        if not sources:
            sources = agent_run.sources
            results = agent_run.raw_results

        answer = agent_run.answer
        model = agent_run.model

        # Command layer: stream the final answer the agent produced.
        # Unified: agent is now the ONLY answer producer.
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
        else:
            # Non-LLM fallback when agent produced nothing.
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

    def _build_agent_tools(self, tool_context: ToolContext) -> list[AgentTool]:
        """Wrap registered tools as AgentTool, narrowed to allowed_tools."""
        descriptions = self.tool_registry.descriptions()
        allowed = self.runtime_config.allowed_tools
        if allowed is not None:
            allowed_set = set(allowed)
            descriptions = [d for d in descriptions if d["name"] in allowed_set]
        return [
            AgentTool(
                name=tool["name"],
                description=tool["description"],
                run=lambda payload, name=tool["name"]: self.tool_registry.run(
                    name,
                    payload,
                    tool_context,
                ),
            )
            for tool in descriptions
        ]

    def _run_agent(
        self,
        *,
        question: str,
        answer_mode: AnswerMode,
        tool_context: ToolContext,
        trace: TraceContext,
        evidence: list[SearchResult] | None = None,
    ) -> AgentRun:
        rc = self.runtime_config
        agent = ReActAgent(
            chat_client=self.chat_client,
            tools=self._build_agent_tools(tool_context),
            max_steps=rc.max_steps,
        )
        deadline = time.perf_counter() + rc.total_timeout_seconds
        attempts = rc.retry_attempts + 1
        with traced_step(self.trace_service, trace, "agent.answer"):
            for attempt in range(attempts):
                try:
                    return agent.run(
                        question=question,
                        answer_mode=answer_mode,
                        evidence=evidence,
                        deadline=deadline,
                    )
                except Exception:
                    if attempt == attempts - 1:
                        return _empty_agent_run()
        return _empty_agent_run()

    def _run_agent_stream(
        self,
        *,
        question: str,
        answer_mode: AnswerMode,
        tool_context: ToolContext,
        evidence: list[SearchResult] | None = None,
    ):
        rc = self.runtime_config
        agent = ReActAgent(
            chat_client=self.chat_client,
            tools=self._build_agent_tools(tool_context),
            max_steps=rc.max_steps,
        )
        deadline = time.perf_counter() + rc.total_timeout_seconds
        yield from agent.run_stream(
            question=question,
            answer_mode=answer_mode,
            evidence=evidence,
            deadline=deadline,
        )

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
                    f"模型生成暂不可用，已使用本地兜底回答。错误信息：{exc}",
                    None,
                )

        return build_template_answer(question, results), None


def build_template_answer(question: str, results: list[SearchResult]) -> str:
    if not results:
        return (
            "未在当前知识库中检索到足够相关的资料。"
            "请先上传企业制度、产品手册或 FAQ 等文档后再提问。"
        )

    evidence = "\n".join(
        f"{index}. {result.chunk.content[:260]}"
        for index, result in enumerate(results[:3], start=1)
    )
    return (
        f"根据知识库中最相关的内容，针对“{question}”可以参考以下资料：\n\n"
        f"{evidence}\n\n"
        "以上内容来自检索到的知识片段，请结合引用来源核验关键信息。"
    )


def chunk_text(text: str, size: int = 48) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


def build_messages(  # deprecated: answer generation is now unified in the ReAct agent.
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
        "请用 3 到 6 个要点简洁回答。"
        if answer_mode == "fast"
        else "请仔细分析证据，然后只输出结构化的最终回答。"
    )
    return [
        {
            "role": "system",
            "content": (
                "You are an enterprise RAG assistant. Answer strictly from the provided "
                "evidence. Do not invent facts outside the evidence. Cite key claims "
                "with references such as [1] or [2]. If evidence is insufficient, say so clearly. "
                "Answer in the same language as the user's question; if the question contains "
                "Chinese, answer in Simplified Chinese."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Answer mode: {answer_mode}\n"
                "Answer language: 跟随用户问题语言；中文问题请使用简体中文。\n"
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
