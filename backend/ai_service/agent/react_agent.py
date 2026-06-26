import json
import time
from inspect import signature
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.ai_service.llm.chat_client import AnswerMode, BailianChatClient
from backend.ai_service.retrieval.vector_store import SearchResult


AgentDecisionType = Literal["action", "final"]


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


class ReActAgent:
    """Prompt-based ReAct loop for models without native tool calling."""

    def __init__(
        self,
        chat_client: BailianChatClient,
        tools: Sequence[AgentTool],
        max_steps: int = 4,
    ) -> None:
        self.chat_client = chat_client
        self.tools = {tool.name: tool for tool in tools}
        self.max_steps = max_steps
        self._supports_native_tools = _supports_complete_tools(chat_client)

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
        """Yield each reasoning step live, then a final run.

        Emits ``{"type": "thought", "step": AgentStep}`` for every ReAct step
        (including the final reasoning step) as it is produced, and finishes
        with ``{"type": "final", "run": AgentRun}``. When the model is disabled
        only the final (empty) run is yielded. ``run`` drains this generator so
        the two paths share one implementation.

        When *evidence* is provided (Route B), pre-fetched knowledge base
        results are injected into the prompt so the agent can answer grounded
        in retrieved evidence.
        """
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

        if self._supports_native_tools:
            yield from self._run_native_tool_stream(
                question=question,
                answer_mode=answer_mode,
                evidence=evidence,
                memory=memory,
                deadline=deadline,
            )
            return

        steps: list[AgentStep] = []
        sources: list[dict] = []
        raw_results: list[SearchResult] = []
        model: str | None = None

        for _ in range(self.max_steps):
            # Runtime-imposed soft deadline: stop calling tools and force a
            # final answer so the run cannot exceed the budget. The deadline is
            # an absolute perf_counter timestamp passed in by the Runtime.
            if deadline is not None and time.perf_counter() >= deadline:
                break
            response = self.chat_client.complete(
                messages=self._build_messages(
                    question,
                    answer_mode,
                    steps,
                    evidence=evidence,
                    memory=memory,
                ),
                mode=answer_mode,
                temperature=0.1 if answer_mode == "thinking" else 0.2,
            )
            model = response.model
            decision = _parse_decision(response.content)
            if decision["type"] == "invalid":
                repair = self._retry_invalid_decision(
                    question=question,
                    answer_mode=answer_mode,
                    steps=steps,
                    bad_content=response.content,
                    error=decision["error"],
                    evidence=evidence,
                    memory=memory,
                    deadline=deadline,
                )
                model = repair.model
                decision = _parse_decision(repair.content)
                if decision["type"] == "invalid":
                    decision = {
                        "type": "final",
                        "thought": "模型连续返回不符合协议的结果，已停止工具循环。",
                        "answer": "抱歉，模型返回的工具调用格式不正确，系统未继续执行检索。请稍后重试。",
                    }

            if decision["type"] == "final":
                final_step = AgentStep(thought=decision["thought"])
                steps.append(final_step)
                yield {"type": "thought", "step": final_step}
                yield {
                    "type": "final",
                    "run": AgentRun(
                        answer=decision["answer"],
                        sources=sources,
                        model=model,
                        steps=steps,
                        raw_results=raw_results,
                    ),
                }
                return

            action = decision["action"]
            tool = self.tools.get(action)
            if not tool:
                observation = f"Unknown tool: {action}"
                step = AgentStep(
                    thought=decision["thought"],
                    action=action,
                    action_input=decision["action_input"],
                    observation=observation,
                )
                steps.append(step)
                yield {"type": "thought", "step": step}
                continue

            result = tool.run(decision["action_input"])
            sources = result.sources or sources
            raw_results = result.raw_results or raw_results
            step = AgentStep(
                thought=decision["thought"],
                action=action,
                action_input=decision["action_input"],
                observation=result.content,
            )
            steps.append(step)
            yield {"type": "thought", "step": step}

        response = self.chat_client.complete(
            messages=self._build_messages(
                question,
                answer_mode,
                steps,
                force_final=True,
                evidence=evidence,
                memory=memory,
            ),
            mode=answer_mode,
            temperature=0.1 if answer_mode == "thinking" else 0.2,
        )
        model = response.model
        decision = _parse_decision(response.content)
        if decision["type"] == "invalid":
            decision = {
                "type": "final",
                "thought": decision["error"],
                "answer": response.content.strip(),
            }
        answer = decision["answer"] if decision["type"] == "final" else response.content
        final_step = AgentStep(thought=decision["thought"])
        steps.append(final_step)
        yield {"type": "thought", "step": final_step}
        yield {
            "type": "final",
            "run": AgentRun(
                answer=answer,
                sources=sources,
                model=model,
                steps=steps,
                raw_results=raw_results,
            ),
        }

    def _run_native_tool_stream(
        self,
        question: str,
        answer_mode: AnswerMode,
        evidence: Sequence[SearchResult] | None = None,
        memory: Sequence[dict] | None = None,
        deadline: float | None = None,
    ):
        steps: list[AgentStep] = []
        sources: list[dict] = []
        raw_results: list[SearchResult] = []
        model: str | None = None
        messages: list[dict[str, Any]] = self._build_native_messages(
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

    def _retry_invalid_decision(
        self,
        question: str,
        answer_mode: AnswerMode,
        steps: Sequence[AgentStep],
        bad_content: str,
        error: str,
        evidence: Sequence[SearchResult] | None = None,
        deadline: float | None = None,
        memory: Sequence[dict] | None = None,
    ):
        if deadline is not None and time.perf_counter() >= deadline:
            return ChatModelResponse(
                content='{"type":"final","thought":"纠错前已达到时间限制。","answer":"抱歉，系统处理超时，请稍后重试。"}',
                reasoning_content=None,
                model="timeout",
            )

        messages = self._build_messages(
            question,
            answer_mode,
            steps,
            evidence=evidence,
            memory=memory,
        )
        messages.append(
            {
                "role": "user",
                "content": (
                    "你的上一次输出不符合工具调用协议，请只重新输出一个合法 JSON，不要解释。\n"
                    f"错误原因：{error}\n"
                    f"上一次输出：{bad_content}\n\n"
                    "合法规则：\n"
                    "1. 如果需要继续检索或调用工具，必须输出："
                    '{"type":"action","thought":"...","action":"knowledge_search","action_input":{"query":"..."}}\n'
                    "2. 如果已经是最终回答，必须输出："
                    '{"type":"final","thought":"...","answer":"..."}\n'
                    "3. final 里禁止出现 action 或 action_input；action 里禁止出现 answer。"
                ),
            }
        )
        return self.chat_client.complete(
            messages=messages,
            mode=answer_mode,
            temperature=0.0,
        )

    def _build_messages(
        self,
        question: str,
        answer_mode: AnswerMode,
        steps: Sequence[AgentStep],
        force_final: bool = False,
        evidence: Sequence[SearchResult] | None = None,
        memory: Sequence[dict] | None = None,
    ) -> list[dict[str, Any]]:
        tool_text = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self.tools.values()
        )
        transcript = _format_steps(steps)
        memory_block = _format_memory(memory)
        language_instruction = _language_instruction(question)
        mode_instruction = (
            "请用 3 到 6 点简洁回答。"
            if answer_mode == "fast"
            else "请仔细分析证据，然后只输出给用户看的最终回答。"
        )
        next_instruction = (
            "现在必须返回最终答案。"
            if force_final
            else "如果还需要证据，只选择一个工具动作；如果证据已足够，就给最终回答。"
        )

        # Evidence routing: Route B (pre-fetched knowledge) vs Route A (no KB).
        if evidence:
            evidence_block = (
                "已检索到的知识库证据（优先作为回答依据）：\n"
                f"{_format_evidence(evidence)}\n\n"
                "请基于这些证据回答，并用 [1]、[2] 等格式标注关键依据。"
                "如果证据不完整，可以继续使用工具。"
            )
            system_suffix = (
                " 已提供知识库证据时，必须严格基于证据和工具观察作答，"
                "不要编造证据之外的企业内部事实。"
            )
        else:
            evidence_block = (
                '本轮未提供可用的知识库证据（可能未检索，或检索后没有命中）。'
                '最终答案必须以这个精确句子开头：'
                '"未在知识库中检索到相关资料。" '
                "然后再基于通用知识回答。不要调用 knowledge_search。"
            )
            system_suffix = ""

        return [
            {
                "role": "system",
                "content": (
                    "你是企业知识库 RAG 助手的 ReAct agent（决策代理）。"
                    "当问题依赖企业内部知识时，要调用工具获取依据。"
                    "不要编造工具观察结果之外的企业内部事实。"
                    "你必须只返回一个 JSON 对象，不能返回 Markdown。\n\n"
                    f"回答语言：{language_instruction}\n"
                    "JSON 字段名保持英文，但 thought 和 answer 的内容使用回答语言。\n\n"
                    "工具调用 JSON 格式：\n"
                    '{"type":"action","thought":"...","action":"tool_name",'
                    '"action_input":{"query":"..."}}\n\n'
                    "最终回答 JSON 格式：\n"
                    '{"type":"final","thought":"...","answer":"..."}\n'
                    "严格规则：\n"
                    "- 需要继续检索或调用工具时，type 必须是 action。\n"
                    "- 已经给最终回答时，type 必须是 final，且必须包含 answer。\n"
                    "- final 中禁止出现 action 或 action_input。\n"
                    "- action 中禁止出现 answer。\n"
                    f"{system_suffix}\n\n"
                    f"可用工具：\n{tool_text}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{question}\n"
                    f"回答模式：{answer_mode}\n"
                    f"回答语言要求：{language_instruction}\n"
                    f"回答要求：{mode_instruction}\n\n"
                    f"{evidence_block}\n\n"
                    f"会话历史：\n{memory_block}\n\n"
                    f"已有步骤：\n{transcript or '（无）'}\n\n"
                    f"{next_instruction}"
                ),
            },
        ]

    def _build_native_messages(
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
                "content": (
                    "你是企业知识库 RAG 助手。你可以使用工具检索企业知识库。"
                    "当问题依赖企业内部资料、制度、流程、产品说明或需要引用依据时，"
                    "优先调用工具。最终回答必须面向用户，使用简体中文，"
                    "并在使用知识库证据时用 [1]、[2] 标注来源。"
                    "不要编造工具结果之外的企业内部事实。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{question}\n"
                    f"回答语言要求：{language_instruction}\n"
                    f"回答要求：{mode_instruction}\n\n"
                    f"会话历史：\n{memory_block}\n\n"
                    f"{evidence_block}"
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


def _parse_decision(content: str) -> dict:
    try:
        payload = json.loads(_extract_json(content))
    except json.JSONDecodeError:
        return {
            "type": "final",
            "thought": "Model returned plain text; treating it as the final answer.",
            "answer": content.strip(),
        }

    decision_type = payload.get("type")
    if decision_type == "action":
        if "answer" in payload:
            return {
                "type": "invalid",
                "error": "action 决策中不能包含 answer 字段。",
            }
        action = str(payload.get("action") or "")
        if not action:
            return {
                "type": "invalid",
                "error": "action 决策缺少 action 字段。",
            }
        action_input = payload.get("action_input")
        if not isinstance(action_input, dict):
            return {
                "type": "invalid",
                "error": "action 决策的 action_input 必须是对象。",
            }
        return {
            "type": "action",
            "thought": str(payload.get("thought") or ""),
            "action": action,
            "action_input": action_input,
        }

    if decision_type == "final":
        if "action" in payload or "action_input" in payload:
            action = str(payload.get("action") or "")
            action_input = payload.get("action_input")
            if action and isinstance(action_input, dict) and "answer" not in payload:
                return {
                    "type": "action",
                    "thought": str(payload.get("thought") or ""),
                    "action": action,
                    "action_input": action_input,
                }
            return {
                "type": "invalid",
                "error": "final 决策中不能包含 action 或 action_input 字段。",
            }
        if "answer" not in payload:
            return {
                "type": "invalid",
                "error": "final 决策缺少 answer 字段。",
            }
        return {
            "type": "final",
            "thought": str(payload.get("thought") or ""),
            "answer": str(payload.get("answer") or "").strip(),
        }

    return {
        "type": "invalid",
        "error": "type 必须是 action 或 final。",
    }


def _extract_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _format_steps(steps: Sequence[AgentStep]) -> str:
    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        lines.append(f"Step {index} thought: {step.thought}")
        if step.action:
            lines.append(f"Step {index} action: {step.action}")
            lines.append(
                f"Step {index} action_input: "
                f"{json.dumps(step.action_input or {}, ensure_ascii=False)}"
            )
        if step.observation:
            lines.append(f"Step {index} observation: {step.observation}")
    return "\n".join(lines)


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


def _supports_complete_tools(chat_client: BailianChatClient) -> bool:
    try:
        params = signature(chat_client.complete).parameters
    except (TypeError, ValueError):
        return False
    return "tools" in params and "tool_choice" in params


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
