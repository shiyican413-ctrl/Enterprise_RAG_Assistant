import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from backend.ai_service.config import DATABASE_URL, HISTORY_FILE


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


class PostgresHistoryService:
    def __init__(self, database_url: str = DATABASE_URL) -> None:
        if not database_url:
            raise RuntimeError("DATABASE_URL is required for PostgreSQL storage")
        self.database_url = database_url
        self._ensure_schema()

    def append_turn(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        conversation_id: str | None = None,
    ) -> dict:
        conversation_id = conversation_id or str(uuid.uuid4())
        turn = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "question": question,
            "answer": answer,
            "sources": sources,
            "created_at": datetime.now(UTC),
        }
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_turns (
                        id, conversation_id, question, answer, sources, created_at
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        turn["id"],
                        turn["conversation_id"],
                        turn["question"],
                        turn["answer"],
                        json.dumps(turn["sources"], ensure_ascii=False),
                        turn["created_at"],
                    ),
                )
            conn.commit()

        return {**turn, "created_at": turn["created_at"].isoformat()}

    def get_conversation(self, conversation_id: str) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, conversation_id::text, question, answer, sources, created_at
                    FROM chat_turns
                    WHERE conversation_id = %s::uuid
                    ORDER BY created_at ASC
                    """,
                    (conversation_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "conversation_id": row[1],
                "question": row[2],
                "answer": row[3],
                "sources": row[4] or [],
                "created_at": row[5].isoformat(),
            }
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_turns (
                        id uuid PRIMARY KEY,
                        conversation_id uuid NOT NULL,
                        question text NOT NULL,
                        answer text NOT NULL,
                        sources jsonb NOT NULL DEFAULT '[]'::jsonb,
                        created_at timestamptz NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chat_turns_conversation_id
                    ON chat_turns (conversation_id, created_at)
                    """
                )
            conn.commit()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL storage requires installing dependency: psycopg[binary]"
            ) from exc
        return psycopg.connect(self.database_url)
