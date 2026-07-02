import json
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.ai_service.llm.chat_client import AnswerMode, BailianChatClient
from backend.ai_service.prompts import render_prompt


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
        chat_client: BailianChatClient | None = None,
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
        memory = memory or []
        # Always prefer LLM planning when the chat client is available.
        if self.enable_llm_planning and self.chat_client and self.chat_client.enabled:
            llm_plan = self._create_llm_plan(
                question=question,
                answer_mode=answer_mode,
                memory=memory,
            )
            if llm_plan is not None:
                return llm_plan

        return self._create_rule_plan(
            question=question,
            answer_mode=answer_mode,
            memory=memory,
        )

    def _create_rule_plan(
        self,
        *,
        question: str,
        answer_mode: AnswerMode,
        memory: list[dict],
    ) -> Plan:
        """Rule fallback — always Route B (knowledge_search then agent) for safety."""
        return Plan(
            question=question,
            answer_mode=answer_mode,
            strategy="rule",
            rationale="Default Route B: planner LLM unavailable.",
            steps=[
                PlanStep(
                    name="tool.knowledge_search",
                    step_type="knowledge_search",
                    input={"query": question},
                ),
                PlanStep(
                    name="agent.answer",
                    step_type="agent_answer",
                    input={
                        "question": question,
                        "answer_mode": answer_mode,
                        "memory_turns": len(memory),
                    },
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
                        "content": render_prompt("planner_system.txt"),
                    },
                    {
                        "role": "user",
                        "content": render_prompt(
                            "planner_user.txt",
                            question=question,
                            answer_mode=answer_mode,
                            memory_turns=len(memory),
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
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

        needs = payload.get("needs_knowledge")
        if needs is None:
            return None

        needs = bool(needs)
        reason = str(payload.get("reason") or "")

        if needs:
            steps = [
                PlanStep(
                    name="tool.knowledge_search",
                    step_type="knowledge_search",
                    input={"query": question},
                ),
                PlanStep(
                    name="agent.answer",
                    step_type="agent_answer",
                    input={"question": question, "answer_mode": answer_mode},
                ),
            ]
            rationale = reason or "LLM planner: knowledge base retrieval required."
        else:
            steps = [
                PlanStep(
                    name="agent.answer",
                    step_type="agent_answer",
                    input={"question": question, "answer_mode": answer_mode},
                ),
            ]
            rationale = reason or "LLM planner: no knowledge base needed."

        return Plan(
            question=question,
            answer_mode=answer_mode,
            steps=steps,
            strategy="llm",
            rationale=rationale,
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
