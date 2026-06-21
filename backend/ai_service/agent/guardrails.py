import re
from dataclasses import dataclass
from collections.abc import Iterable


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str = ""


# Prompt-injection signatures. Kept deliberately conservative so legitimate
# enterprise questions never trip them — these only match explicit attempts to
# override the system prompt. Detection is pure code/regex, never the LLM
# (see docs/agent改进.md §2: security screening must not be delegated to the model).
_DEFAULT_INJECTION_PATTERNS: tuple[str, ...] = (
    r"ignore\s+(?:(?:all|previous|prior|above)\s+)+(?:instructions?|prompts?|rules)",
    r"disregard\s+(?:the\s+|all\s+)?(?:above|previous|prior)\s+(?:instructions?|rules)",
    r"forget\s+(?:everything|all|your\s+(?:previous|prior))?\s*instructions",
    r"you\s+are\s+now\s+(?:a|an)\b",
    r"(?:reveal|show|print|output|repeat)\s+(?:your\s+)?(?:system\s+)?prompt",
    r"<\|im_start\|>|<\|im_end\|>",
    r"\[system\]|\(system\)",
    r"new\s+instructions?\s*:",
    # 中文注入模式
    r"忽略(?:上面|之前|以上|前面)(?:的)?(?:指令|规则|提示|设定)",
    r"忘记(?:你的|之前|前面|上面)?(?:指令|设定|规则|身份)",
    r"从现在起你(?:是|扮演|将)",
    r"输出(?:你的)?(?:系统)?(?:提示|指令)",
)


class GuardrailService:
    """Input-side safety screen. Deterministic only — no model calls."""

    def __init__(
        self,
        *,
        max_length: int = 8000,
        blocked_phrases: Iterable[str] = (),
        injection_patterns: Iterable[str] | None = None,
    ) -> None:
        self.max_length = max_length
        self.blocked_phrases = tuple(p.lower() for p in blocked_phrases if p.strip())
        patterns = (
            tuple(injection_patterns)
            if injection_patterns is not None
            else _DEFAULT_INJECTION_PATTERNS
        )
        self._injection_re = re.compile("|".join(patterns), re.IGNORECASE)

    def validate_chat_input(self, question: str) -> GuardrailResult:
        if not question or not question.strip():
            return GuardrailResult(allowed=False, reason="Question cannot be empty.")

        if len(question) > self.max_length:
            return GuardrailResult(allowed=False, reason="Question is too long.")

        match = self._injection_re.search(question)
        if match:
            return GuardrailResult(
                allowed=False,
                reason="Input rejected: potential prompt-injection detected.",
            )

        lowered = question.lower()
        for phrase in self.blocked_phrases:
            if phrase in lowered:
                return GuardrailResult(
                    allowed=False,
                    reason=f"Input rejected: blocked phrase matched ({phrase!r}).",
                )

        return GuardrailResult(allowed=True)
