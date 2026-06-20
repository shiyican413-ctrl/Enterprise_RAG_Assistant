from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str = ""


class GuardrailService:
    def validate_chat_input(self, question: str) -> GuardrailResult:
        if not question.strip():
            return GuardrailResult(allowed=False, reason="Question cannot be empty.")
        if len(question) > 8000:
            return GuardrailResult(allowed=False, reason="Question is too long.")
        return GuardrailResult(allowed=True)
