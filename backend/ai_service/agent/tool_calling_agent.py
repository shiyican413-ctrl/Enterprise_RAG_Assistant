import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from backend.ai_service.llm.chat_client import AnswerMode, BailianChatClient
from backend.ai_service.prompts import render_prompt
from backend.ai_service.retrieval.vector_store import SearchResult


@dataclass(frozen=True)
class ToolResult:
    content: str
    sources: list[dict] = field(default_factory=list)
    raw_results: list[SearchResult] = field(default_factory=list)


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    run: Callable[[dict], ToolResult]


@dataclass(frozen=True)
class AgentStep:
    thought: str
    action: str | None = None
    action_input: dict | None = None
    observation: str | None = None


@dataclass(frozen=True)
class AgentRun:
    answer: str
    sources: list[dict]
    model: str | None
    steps: list[AgentStep]
    raw_results: list[SearchResult]


class ToolCallingAgent:
    """Native tool-calling agent for enterprise RAG answers."""

    def __init__(
        self,
        chat_client: BailianChatClient,
        tools: Sequence[AgentTool],
        max_steps: int = 4,
    ) -> None:
        self.chat_client = chat_client
        self.tools = {tool.name: tool for tool in tools}
        self.max_steps = max_steps

    def run(
        self,
        question: str,
        answer_mode: AnswerMode,
        evidence: Sequence[SearchResult] | None = None,
        memory: Sequence[dict] | None = None,
        deadline: float | None = None,
    ) -> AgentRun:
        final_run: AgentRun | None = None
        for item in self.run_stream(
            question=question,
            answer_mode=answer_mode,
            evidence=evidence,
            memory=memory,
            deadline=deadline,
        ):
            if item["type"] == "final":
                final_run = item["run"]
        return final_run or AgentRun(
            answer="",
            sources=[],
            model=None,
            steps=[],
            raw_results=[],
        )

    def run_stream(
        self,
        question: str,
        answer_mode: AnswerMode,
        evidence: Sequence[SearchResult] | None = None,
        memory: Sequence[dict] | None = None,
        deadline: float | None = None,
    ):
        """Yield native tool-calling steps live, then a final run."""
        if not self.chat_client.enabled:
            yield {
                "type": "final",
                "run": AgentRun(
                    answer="",
                    sources=[],
                    model=None,
                    steps=[],
                    raw_results=[],
                ),
            }
            return

        steps: list[AgentStep] = []
        sources: list[dict] = []
        raw_results: list[SearchResult] = []
        model: str | None = None
        messages: list[dict[str, Any]] = self._build_messages(
            question=question,
            answer_mode=answer_mode,
            evidence=evidence,
            memory=memory,
        )

        for _ in range(self.max_steps):
            if deadline is not None and time.perf_counter() >= deadline:
                break

            response = self.chat_client.complete(
                messages=messages,
                mode=answer_mode,
                temperature=0.1 if answer_mode == "thinking" else 0.2,
                tools=_tool_schemas(self.tools.values()),
                tool_choice="auto",
            )
            model = response.model
            tool_calls = response.tool_calls or []
            if not tool_calls:
                final_step = AgentStep(thought="模型已返回最终回答。")
                steps.append(final_step)
                yield {"type": "thought", "step": final_step}
                yield {
                    "type": "final",
                    "run": AgentRun(
                        answer=response.content.strip(),
                        sources=sources,
                        model=model,
                        steps=steps,
                        raw_results=raw_results,
                    ),
                }
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": tool_calls,
                }
            )
            for tool_call in tool_calls:
                action, action_input = _parse_tool_call(tool_call)
                tool = self.tools.get(action)
                if not tool:
                    observation = f"Unknown tool: {action}"
                    step = AgentStep(
                        thought=f"模型请求调用未知工具：{action}",
                        action=action,
                        action_input=action_input,
                        observation=observation,
                    )
                    steps.append(step)
                    messages.append(_tool_message(tool_call, observation))
                    yield {"type": "thought", "step": step}
                    continue

                result = tool.run(action_input)
                sources = result.sources or sources
                raw_results = result.raw_results or raw_results
                step = AgentStep(
                    thought=f"模型请求调用工具：{action}",
                    action=action,
                    action_input=action_input,
                    observation=result.content,
                )
                steps.append(step)
                messages.append(_tool_message(tool_call, result.content))
                yield {"type": "thought", "step": step}

        response = self.chat_client.complete(
            messages=[
                *messages,
                {
                    "role": "user",
                    "content": "工具调用步数已达到上限。请基于已有证据给出最终回答，不要再调用工具。",
                },
            ],
            mode=answer_mode,
            temperature=0.1 if answer_mode == "thinking" else 0.2,
        )
        model = response.model
        final_step = AgentStep(thought="工具调用达到上限，强制生成最终回答。")
        steps.append(final_step)
        yield {"type": "thought", "step": final_step}
        yield {
            "type": "final",
            "run": AgentRun(
                answer=response.content.strip(),
                sources=sources,
                model=model,
                steps=steps,
                raw_results=raw_results,
            ),
        }

    def _build_messages(
        self,
        question: str,
        answer_mode: AnswerMode,
        evidence: Sequence[SearchResult] | None = None,
        memory: Sequence[dict] | None = None,
    ) -> list[dict[str, Any]]:
        language_instruction = _language_instruction(question)
        mode_instruction = (
            "请用 3 到 6 点简洁回答。"
            if answer_mode == "fast"
            else "请仔细分析证据，然后只输出给用户看的最终回答。"
        )
        evidence_block = (
            "已检索到的知识库证据（优先作为回答依据）：\n"
            f"{_format_evidence(evidence)}"
            if evidence
            else "本轮未提供可用的知识库证据。若问题依赖企业内部资料，请调用 knowledge_search。"
        )
        memory_block = _format_memory(memory)
        return [
            {
                "role": "system",
                "content": render_prompt("agent_system.txt"),
            },
            {
                "role": "user",
                "content": render_prompt(
                    "agent_user.txt",
                    question=question,
                    language_instruction=language_instruction,
                    mode_instruction=mode_instruction,
                    memory_block=memory_block,
                    evidence_block=evidence_block,
                ),
            },
        ]


def _format_evidence(results: Sequence[SearchResult]) -> str:
    """Format pre-fetched search results into a numbered evidence block."""
    return "\n\n".join(
        f"[{i}] 来源：{r.chunk.document_name}，片段：{r.chunk.chunk_index}\n"
        f"{r.chunk.content[:1200]}"
        for i, r in enumerate(results, start=1)
    )


def _language_instruction(question: str) -> str:
    if _contains_cjk(question):
        return "请使用简体中文回答，除非用户明确要求其他语言。"
    return "Match the user's language unless the user explicitly asks for another language."


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _format_memory(memory: Sequence[dict] | None, max_turns: int = 6) -> str:
    turns = list(memory or [])[-max_turns:]
    if not turns:
        return "（无）"

    lines: list[str] = []
    for index, turn in enumerate(turns, start=1):
        question = str(turn.get("question") or "").strip()
        answer = str(turn.get("answer") or "").strip()
        if len(question) > 500:
            question = f"{question[:500]}..."
        if len(answer) > 1000:
            answer = f"{answer[:1000]}..."
        lines.append(f"历史第 {index} 轮用户：{question}")
        lines.append(f"历史第 {index} 轮助手：{answer}")
    return "\n".join(lines)


def _tool_schemas(tools: Sequence[AgentTool]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "用于检索企业知识库的查询语句。",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
        for tool in tools
    ]


def _parse_tool_call(tool_call: dict[str, Any]) -> tuple[str, dict]:
    function = tool_call.get("function") or {}
    name = str(function.get("name") or "")
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            payload = json.loads(arguments)
        except json.JSONDecodeError:
            payload = {}
    elif isinstance(arguments, dict):
        payload = arguments
    else:
        payload = {}
    return name, payload


def _tool_message(tool_call: dict[str, Any], content: str) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id") or "",
        "content": content,
    }
