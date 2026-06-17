import json
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.ai_service.services.chat_model_service import AnswerMode, DoubaoChatClient


PlanStepType = Literal["agent_answer", "knowledge_search", "answer_generation"]
PlanStrategy = Literal["rule", "llm"]


@dataclass(frozen=True)
class PlanStep:
    name: str
    step_type: PlanStepType
    input: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    question: str
    answer_mode: AnswerMode
    steps: list[PlanStep]
    strategy: PlanStrategy = "rule"
    rationale: str = ""


class PlannerService:
    def __init__(
        self,
        *,
        chat_client: DoubaoChatClient | None = None,
        enable_llm_planning: bool = True,
    ) -> None:
        self.chat_client = chat_client
        self.enable_llm_planning = enable_llm_planning

    def create_plan(
        self,
        *,
        question: str,
        answer_mode: AnswerMode,
        memory: list[dict] | None = None,
    ) -> Plan:
        if self._should_use_llm(question, memory):
            llm_plan = self._create_llm_plan(
                question=question,
                answer_mode=answer_mode,
                memory=memory or [],
            )
            if llm_plan:
                return llm_plan

        return self._create_rule_plan(
            question=question,
            answer_mode=answer_mode,
            memory=memory or [],
        )

    def _create_rule_plan(
        self,
        *,
        question: str,
        answer_mode: AnswerMode,
        memory: list[dict],
    ) -> Plan:
        return Plan(
            question=question,
            answer_mode=answer_mode,
            strategy="rule",
            rationale="Default enterprise RAG route.",
            steps=[
                PlanStep(
                    name="agent.answer",
                    step_type="agent_answer",
                    input={
                        "question": question,
                        "answer_mode": answer_mode,
                        "memory_turns": len(memory),
                    },
                ),
                PlanStep(
                    name="tool.knowledge_search",
                    step_type="knowledge_search",
                    input={"query": question},
                ),
                PlanStep(
                    name="model.answer",
                    step_type="answer_generation",
                    input={"question": question, "answer_mode": answer_mode},
                ),
            ],
        )

    def _create_llm_plan(
        self,
        *,
        question: str,
        answer_mode: AnswerMode,
        memory: list[dict],
    ) -> Plan | None:
        if not self.chat_client or not self.chat_client.enabled:
            return None

        try:
            response = self.chat_client.complete(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a planning module for an enterprise RAG system. "
                            "Return exactly one JSON object. Do not execute tools. "
                            "Allowed step types are: agent_answer, knowledge_search, answer_generation. "
                            "Keep plans short and deterministic."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question: {question}\n"
                            f"Answer mode: {answer_mode}\n"
                            f"Memory turns available: {len(memory)}\n\n"
                            "Return JSON shape: "
                            '{"rationale":"...","steps":[{"name":"agent.answer",'
                            '"step_type":"agent_answer","input":{}}]}'
                        ),
                    },
                ],
                mode=answer_mode,
                temperature=0.0,
            )
        except Exception:
            return None

        try:
            payload = json.loads(_extract_json(response.content))
            steps = [
                PlanStep(
                    name=str(item.get("name") or item.get("step_type") or ""),
                    step_type=item.get("step_type"),
                    input=item.get("input") or {},
                )
                for item in payload.get("steps", [])
                if item.get("step_type") in {"agent_answer", "knowledge_search", "answer_generation"}
            ]
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

        if not steps:
            return None

        return Plan(
            question=question,
            answer_mode=answer_mode,
            steps=steps,
            strategy="llm",
            rationale=str(payload.get("rationale") or "LLM planner selected route."),
        )

    def _should_use_llm(self, question: str, memory: list[dict] | None) -> bool:
        if not self.enable_llm_planning:
            return False
        if not self.chat_client or not self.chat_client.enabled:
            return False

        text = question.lower()
        complex_markers = (
            "compare",
            "summarize",
            "analyze",
            "plan",
            "steps",
            "multiple",
            "difference",
            "why",
            "how should",
        )
        return len(question) > 120 or len(memory or []) >= 3 or any(
            marker in text for marker in complex_markers
        )


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
