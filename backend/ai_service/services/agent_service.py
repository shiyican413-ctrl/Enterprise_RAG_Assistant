import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from backend.ai_service.services.chat_model_service import AnswerMode, DoubaoChatClient
from backend.ai_service.services.vector_store_service import SearchResult


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
        chat_client: DoubaoChatClient,
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
    ) -> AgentRun:
        final_run: AgentRun | None = None
        for item in self.run_stream(question=question, answer_mode=answer_mode):
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
    ):
        """Yield each reasoning step live, then a final run.

        Emits ``{"type": "thought", "step": AgentStep}`` for every ReAct step
        (including the final reasoning step) as it is produced, and finishes
        with ``{"type": "final", "run": AgentRun}``. When the model is disabled
        only the final (empty) run is yielded. ``run`` drains this generator so
        the two paths share one implementation.
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
            response = self.chat_client.complete(
                messages=self._build_messages(question, answer_mode, steps),
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
            messages=self._build_messages(question, answer_mode, steps, force_final=True),
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
    ) -> list[dict[str, str]]:
        tool_text = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self.tools.values()
        )
        transcript = _format_steps(steps)
        mode_instruction = (
            "Give a concise answer in 3 to 6 points."
            if answer_mode == "fast"
            else "Analyze carefully, then provide only the final answer to the user."
        )
        next_instruction = (
            "You must now return a final answer."
            if force_final
            else "Choose one tool action if more evidence is needed; otherwise answer."
        )

        return [
            {
                "role": "system",
                "content": (
                    "You are an enterprise RAG ReAct agent. Use tools when the answer "
                    "depends on private knowledge. Do not invent facts outside tool "
                    "observations. Respond with exactly one JSON object and no markdown.\n\n"
                    "Action JSON shape:\n"
                    '{"type":"action","thought":"...","action":"tool_name",'
                    '"action_input":{"query":"..."}}\n\n'
                    "Final JSON shape:\n"
                    '{"type":"final","thought":"...","answer":"..."}\n\n'
                    f"Available tools:\n{tool_text}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"Answer mode: {answer_mode}\n"
                    f"Answer requirement: {mode_instruction}\n"
                    f"Previous steps:\n{transcript or '(none)'}\n\n"
                    f"{next_instruction}"
                ),
            },
        ]


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
