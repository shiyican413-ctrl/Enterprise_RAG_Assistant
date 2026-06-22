import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

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

    def run(
        self,
        question: str,
        answer_mode: AnswerMode,
        evidence: Sequence[SearchResult] | None = None,
        deadline: float | None = None,
    ) -> AgentRun:
        final_run: AgentRun | None = None
        for item in self.run_stream(
            question=question, answer_mode=answer_mode, evidence=evidence, deadline=deadline,
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
                messages=self._build_messages(question, answer_mode, steps, evidence=evidence),
                mode=answer_mode,
                temperature=0.1 if answer_mode == "thinking" else 0.2,
            )
            model = response.model
            decision = _parse_decision(response.content)

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
            messages=self._build_messages(question, answer_mode, steps, force_final=True, evidence=evidence),
            mode=answer_mode,
            temperature=0.1 if answer_mode == "thinking" else 0.2,
        )
        model = response.model
        decision = _parse_decision(response.content)
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

    def _build_messages(
        self,
        question: str,
        answer_mode: AnswerMode,
        steps: Sequence[AgentStep],
        force_final: bool = False,
        evidence: Sequence[SearchResult] | None = None,
    ) -> list[dict[str, str]]:
        tool_text = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self.tools.values()
        )
        transcript = _format_steps(steps)
        language_instruction = _language_instruction(question)
        mode_instruction = (
            "请用 3 到 6 点简洁回答。"
            if answer_mode == "fast"
            else "请仔细分析证据，然后只输出给用户看的最终回答。"
        )
        next_instruction = (
            "You must now return a final answer."
            if force_final
            else "Choose one tool action if more evidence is needed; otherwise answer."
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
                " When retrieved evidence is provided, answer strictly from it; "
                "do not invent facts outside the evidence and your tool observations."
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
                    "You are an enterprise RAG ReAct agent. Use tools when the answer "
                    "depends on private knowledge. Do not invent facts outside tool "
                    "observations. Respond with exactly one JSON object and no markdown.\n\n"
                    f"Answer language: {language_instruction}\n"
                    "Keep JSON keys in English, but write thought and answer values in the answer language.\n\n"
                    "Action JSON shape:\n"
                    '{"type":"action","thought":"...","action":"tool_name",'
                    '"action_input":{"query":"..."}}\n\n'
                    "Final JSON shape:\n"
                    '{"type":"final","thought":"...","answer":"..."}\n'
                    f"{system_suffix}\n\n"
                    f"Available tools:\n{tool_text}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"Answer mode: {answer_mode}\n"
                    f"Answer language requirement: {language_instruction}\n"
                    f"Answer requirement: {mode_instruction}\n\n"
                    f"{evidence_block}\n\n"
                    f"Previous steps:\n{transcript or '(none)'}\n\n"
                    f"{next_instruction}"
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
        return {
            "type": "action",
            "thought": str(payload.get("thought") or ""),
            "action": str(payload.get("action") or ""),
            "action_input": payload.get("action_input") or {},
        }

    return {
        "type": "final",
        "thought": str(payload.get("thought") or ""),
        "answer": str(payload.get("answer") or content).strip(),
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
