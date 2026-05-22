import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from backend.ai_service.config import HISTORY_FILE


class HistoryService:
    def __init__(self, history_file: Path = HISTORY_FILE) -> None:
        self.history_file = history_file
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def append_turn(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        conversation_id: str | None = None,
    ) -> dict:
        conversation_id = conversation_id or str(uuid.uuid4())
        histories = self._load()
        turn = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "question": question,
            "answer": answer,
            "sources": sources,
            "created_at": datetime.now(UTC).isoformat(),
        }
        histories.append(turn)
        self._save(histories)
        return turn

    def get_conversation(self, conversation_id: str) -> list[dict]:
        return [
            item
            for item in self._load()
            if item.get("conversation_id") == conversation_id
        ]

    def _load(self) -> list[dict]:
        if not self.history_file.exists():
            return []
        return json.loads(self.history_file.read_text(encoding="utf-8"))

    def _save(self, histories: list[dict]) -> None:
        self.history_file.write_text(
            json.dumps(histories, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
