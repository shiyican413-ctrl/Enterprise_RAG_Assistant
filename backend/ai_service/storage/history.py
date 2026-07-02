import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from backend.ai_service.core.config import DATABASE_URL, DEFAULT_TENANT_ID, HISTORY_FILE


def _conversation_title(question: str) -> str:
    title = " ".join(question.strip().split())
    if not title:
        return "新对话"
    return title if len(title) <= 30 else f"{title[:30]}..."


class HistoryService:
    def __init__(self, history_file: Path = HISTORY_FILE) -> None:
        self.history_file = history_file
        self.conversations_file = history_file.with_name("conversations.json")
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def append_turn(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        conversation_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        model: str | None = None,
        answer_mode: str | None = None,
        trace_id: str | None = None,
        route: list[dict] | None = None,
        agent_steps: list[dict] | None = None,
    ) -> dict:
        conversation_id = conversation_id or str(uuid.uuid4())
        histories = self._load()
        conversations = self._load_conversations()
        now = datetime.now(UTC).isoformat()
        conversation = self._find_conversation(conversations, conversation_id)
        if conversation is None:
            conversations.append(
                {
                    "id": conversation_id,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "tenant_id": tenant_id or DEFAULT_TENANT_ID,
                    "title": _conversation_title(question),
                    "summary": "",
                    "pinned": False,
                    "archived": False,
                    "message_count": 0,
                    "created_at": now,
                    "updated_at": now,
                    "last_message_at": now,
                    "last_question": question,
                }
            )
        else:
            conversation["updated_at"] = now
            conversation["last_message_at"] = now
            conversation["last_question"] = question
        self._find_conversation(conversations, conversation_id)["message_count"] = (
            self._count_turns(histories, conversation_id) + 1
        )

        turn = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "user_id": user_id,
            "tenant_id": tenant_id or DEFAULT_TENANT_ID,
            "question": question,
            "answer": answer,
            "sources": sources,
            "model": model,
            "answer_mode": answer_mode,
            "trace_id": trace_id,
            "route": route or [],
            "agent_steps": agent_steps or [],
            "created_at": now,
        }
        histories.append(turn)
        self._save(histories)
        self._save_conversations(conversations)
        return turn

    def get_conversation(
        self, conversation_id: str, user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict]:
        return [
            item
            for item in self._load()
            if item.get("conversation_id") == conversation_id
            and (user_id is None or item.get("user_id") == user_id)
            and (
                tenant_id is None
                or item.get("tenant_id", DEFAULT_TENANT_ID) == tenant_id
            )
        ]

    def list_conversations(
        self,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        conversations = self._load_conversations()
        normalized_query = query.strip().lower() if query else ""
        filtered = [
            item
            for item in conversations
            if (user_id is None or item.get("user_id") == user_id)
            and (
                tenant_id is None
                or item.get("tenant_id", DEFAULT_TENANT_ID) == tenant_id
            )
            and not item.get("archived", False)
            and (
                not normalized_query
                or normalized_query in str(item.get("title", "")).lower()
                or normalized_query in str(item.get("last_question", "")).lower()
                or normalized_query in str(item.get("summary", "")).lower()
            )
        ]
        filtered.sort(
            key=lambda item: item.get("last_message_at") or item.get("updated_at") or "",
            reverse=True,
        )
        return filtered[:limit]

    def update_conversation(
        self,
        conversation_id: str,
        *,
        title: str | None = None,
        pinned: bool | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict | None:
        conversations = self._load_conversations()
        conversation = self._find_authorized_conversation(
            conversations, conversation_id, user_id=user_id, tenant_id=tenant_id
        )
        if conversation is None:
            return None
        if title is not None:
            conversation["title"] = title.strip() or conversation.get("title") or "新对话"
        if pinned is not None:
            conversation["pinned"] = pinned
        conversation["updated_at"] = datetime.now(UTC).isoformat()
        self._save_conversations(conversations)
        return conversation

    def delete_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> bool:
        conversations = self._load_conversations()
        conversation = self._find_authorized_conversation(
            conversations, conversation_id, user_id=user_id, tenant_id=tenant_id
        )
        if conversation is None:
            return False
        self._save_conversations(
            [item for item in conversations if item.get("conversation_id", item.get("id")) != conversation_id]
        )
        self._save(
            [item for item in self._load() if item.get("conversation_id") != conversation_id]
        )
        return True

    def _load(self) -> list[dict]:
        if not self.history_file.exists():
            return []
        return json.loads(self.history_file.read_text(encoding="utf-8"))

    def _save(self, histories: list[dict]) -> None:
        self.history_file.write_text(
            json.dumps(histories, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_conversations(self) -> list[dict]:
        if self.conversations_file.exists():
            return json.loads(self.conversations_file.read_text(encoding="utf-8"))
        return self._derive_conversations(self._load())

    def _save_conversations(self, conversations: list[dict]) -> None:
        self.conversations_file.write_text(
            json.dumps(conversations, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _derive_conversations(self, histories: list[dict]) -> list[dict]:
        conversations: dict[str, dict] = {}
        for turn in histories:
            conversation_id = turn.get("conversation_id")
            if not conversation_id:
                continue
            existing = conversations.get(conversation_id)
            created_at = turn.get("created_at") or datetime.now(UTC).isoformat()
            if existing is None:
                conversations[conversation_id] = {
                    "id": conversation_id,
                    "conversation_id": conversation_id,
                    "user_id": turn.get("user_id"),
                    "tenant_id": turn.get("tenant_id", DEFAULT_TENANT_ID),
                    "title": _conversation_title(str(turn.get("question") or "")),
                    "summary": "",
                    "pinned": False,
                    "archived": False,
                    "message_count": 1,
                    "created_at": created_at,
                    "updated_at": created_at,
                    "last_message_at": created_at,
                    "last_question": turn.get("question") or "",
                }
            else:
                existing["message_count"] = int(existing.get("message_count") or 0) + 1
                existing["updated_at"] = created_at
                existing["last_message_at"] = created_at
                existing["last_question"] = turn.get("question") or ""
        return list(conversations.values())

    def _find_conversation(
        self, conversations: list[dict], conversation_id: str
    ) -> dict | None:
        for item in conversations:
            if item.get("conversation_id", item.get("id")) == conversation_id:
                return item
        return None

    def _find_authorized_conversation(
        self,
        conversations: list[dict],
        conversation_id: str,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict | None:
        conversation = self._find_conversation(conversations, conversation_id)
        if conversation is None:
            return None
        if user_id is not None and conversation.get("user_id") != user_id:
            return None
        if tenant_id is not None and conversation.get("tenant_id", DEFAULT_TENANT_ID) != tenant_id:
            return None
        return conversation

    def _count_turns(self, histories: list[dict], conversation_id: str) -> int:
        return sum(1 for item in histories if item.get("conversation_id") == conversation_id)


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
        user_id: str | None = None,
        tenant_id: str | None = None,
        model: str | None = None,
        answer_mode: str | None = None,
        trace_id: str | None = None,
        route: list[dict] | None = None,
        agent_steps: list[dict] | None = None,
    ) -> dict:
        conversation_id = conversation_id or str(uuid.uuid4())
        now = datetime.now(UTC)
        turn = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "user_id": user_id,
            "tenant_id": tenant_id or DEFAULT_TENANT_ID,
            "question": question,
            "answer": answer,
            "sources": sources,
            "model": model,
            "answer_mode": answer_mode,
            "trace_id": trace_id,
            "route": route or [],
            "agent_steps": agent_steps or [],
            "created_at": now,
        }
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_conversations (
                        id, tenant_id, user_id, title, summary, pinned, archived,
                        message_count, created_at, updated_at, last_message_at, last_question
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, '', false, false,
                        0, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        updated_at = EXCLUDED.updated_at,
                        last_message_at = EXCLUDED.last_message_at,
                        last_question = EXCLUDED.last_question
                    """,
                    (
                        turn["conversation_id"],
                        turn["tenant_id"],
                        turn["user_id"],
                        _conversation_title(question),
                        now,
                        now,
                        now,
                        question,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO chat_turns (
                        id, conversation_id, user_id, tenant_id, question, answer, sources,
                        model, answer_mode, trace_id, route, agent_steps, created_at
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb,
                        %s, %s, %s::uuid, %s::jsonb, %s::jsonb, %s
                    )
                    """,
                    (
                        turn["id"],
                        turn["conversation_id"],
                        turn["user_id"],
                        turn["tenant_id"],
                        turn["question"],
                        turn["answer"],
                        json.dumps(turn["sources"], ensure_ascii=False),
                        turn["model"],
                        turn["answer_mode"],
                        turn["trace_id"],
                        json.dumps(turn["route"], ensure_ascii=False),
                        json.dumps(turn["agent_steps"], ensure_ascii=False),
                        turn["created_at"],
                    ),
                )
                cur.execute(
                    """
                    UPDATE chat_conversations
                    SET message_count = (
                        SELECT count(*) FROM chat_turns WHERE conversation_id = %s::uuid
                    )
                    WHERE id = %s::uuid
                    """,
                    (turn["conversation_id"], turn["conversation_id"]),
                )
            conn.commit()

        return {**turn, "created_at": turn["created_at"].isoformat()}

    def get_conversation(
        self, conversation_id: str, user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, conversation_id::text, user_id::text, tenant_id::text,
                           question, answer, sources, created_at, model, answer_mode,
                           trace_id::text, route, agent_steps
                    FROM chat_turns
                    WHERE conversation_id = %s::uuid
                      AND (%s::uuid IS NULL OR user_id = %s::uuid)
                      AND (%s::uuid IS NULL OR tenant_id = %s::uuid)
                    ORDER BY created_at ASC
                    """,
                    (conversation_id, user_id, user_id, tenant_id, tenant_id),
                )
                rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "conversation_id": row[1],
                "user_id": row[2],
                "tenant_id": row[3],
                "question": row[4],
                "answer": row[5],
                "sources": row[6] or [],
                "created_at": row[7].isoformat(),
                "model": row[8],
                "answer_mode": row[9],
                "trace_id": row[10],
                "route": row[11] or [],
                "agent_steps": row[12] or [],
            }
            for row in rows
        ]

    def list_conversations(
        self,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        normalized_query = f"%{query.strip()}%" if query and query.strip() else None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, user_id::text, tenant_id::text, title, summary,
                           pinned, archived, message_count, created_at, updated_at,
                           last_message_at, last_question
                    FROM chat_conversations
                    WHERE (%s::uuid IS NULL OR user_id = %s::uuid)
                      AND (%s::uuid IS NULL OR tenant_id = %s::uuid)
                      AND archived = false
                      AND (
                        %s IS NULL
                        OR title ILIKE %s
                        OR last_question ILIKE %s
                        OR summary ILIKE %s
                      )
                    ORDER BY pinned DESC, last_message_at DESC NULLS LAST, updated_at DESC
                    LIMIT %s
                    """,
                    (
                        user_id,
                        user_id,
                        tenant_id,
                        tenant_id,
                        normalized_query,
                        normalized_query,
                        normalized_query,
                        normalized_query,
                        limit,
                    ),
                )
                rows = cur.fetchall()
        return [self._conversation_from_row(row) for row in rows]

    def update_conversation(
        self,
        conversation_id: str,
        *,
        title: str | None = None,
        pinned: bool | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict | None:
        updates = []
        params: list[object] = []
        if title is not None:
            updates.append("title = %s")
            params.append(title.strip() or "新对话")
        if pinned is not None:
            updates.append("pinned = %s")
            params.append(pinned)
        updates.append("updated_at = %s")
        params.append(datetime.now(UTC))
        params.extend([conversation_id, user_id, user_id, tenant_id, tenant_id])
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE chat_conversations
                    SET {", ".join(updates)}
                    WHERE id = %s::uuid
                      AND (%s::uuid IS NULL OR user_id = %s::uuid)
                      AND (%s::uuid IS NULL OR tenant_id = %s::uuid)
                    RETURNING id::text, user_id::text, tenant_id::text, title, summary,
                              pinned, archived, message_count, created_at, updated_at,
                              last_message_at, last_question
                    """,
                    params,
                )
                row = cur.fetchone()
            conn.commit()
        return self._conversation_from_row(row) if row else None

    def delete_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM chat_conversations
                    WHERE id = %s::uuid
                      AND (%s::uuid IS NULL OR user_id = %s::uuid)
                      AND (%s::uuid IS NULL OR tenant_id = %s::uuid)
                    RETURNING id
                    """,
                    (conversation_id, user_id, user_id, tenant_id, tenant_id),
                )
                deleted = cur.fetchone() is not None
                if deleted:
                    cur.execute(
                        "DELETE FROM chat_turns WHERE conversation_id = %s::uuid",
                        (conversation_id,),
                    )
            conn.commit()
        return deleted

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_conversations (
                        id uuid PRIMARY KEY,
                        tenant_id uuid NOT NULL,
                        user_id uuid,
                        title text NOT NULL,
                        summary text NOT NULL DEFAULT '',
                        pinned boolean NOT NULL DEFAULT false,
                        archived boolean NOT NULL DEFAULT false,
                        message_count integer NOT NULL DEFAULT 0,
                        created_at timestamptz NOT NULL,
                        updated_at timestamptz NOT NULL,
                        last_message_at timestamptz,
                        last_question text NOT NULL DEFAULT ''
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_turns (
                        id uuid PRIMARY KEY,
                        conversation_id uuid NOT NULL,
                        user_id uuid,
                        tenant_id uuid,
                        question text NOT NULL,
                        answer text NOT NULL,
                        sources jsonb NOT NULL DEFAULT '[]'::jsonb,
                        model text,
                        answer_mode text,
                        trace_id uuid,
                        route jsonb NOT NULL DEFAULT '[]'::jsonb,
                        agent_steps jsonb NOT NULL DEFAULT '[]'::jsonb,
                        created_at timestamptz NOT NULL
                    )
                    """
                )
                cur.execute("ALTER TABLE chat_turns ADD COLUMN IF NOT EXISTS user_id uuid")
                cur.execute("ALTER TABLE chat_turns ADD COLUMN IF NOT EXISTS tenant_id uuid")
                cur.execute("ALTER TABLE chat_turns ADD COLUMN IF NOT EXISTS model text")
                cur.execute("ALTER TABLE chat_turns ADD COLUMN IF NOT EXISTS answer_mode text")
                cur.execute("ALTER TABLE chat_turns ADD COLUMN IF NOT EXISTS trace_id uuid")
                cur.execute(
                    "ALTER TABLE chat_turns ADD COLUMN IF NOT EXISTS route jsonb NOT NULL DEFAULT '[]'::jsonb"
                )
                cur.execute(
                    "ALTER TABLE chat_turns ADD COLUMN IF NOT EXISTS agent_steps jsonb NOT NULL DEFAULT '[]'::jsonb"
                )
                cur.execute(
                    "UPDATE chat_turns SET tenant_id=%s::uuid WHERE tenant_id IS NULL",
                    (DEFAULT_TENANT_ID,),
                )
                cur.execute("ALTER TABLE chat_turns ALTER COLUMN tenant_id SET NOT NULL")
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chat_turns_conversation_id
                    ON chat_turns (conversation_id, created_at)
                    """
                )
                cur.execute(
                    """
                    INSERT INTO chat_conversations (
                        id, tenant_id, user_id, title, summary, pinned, archived,
                        message_count, created_at, updated_at, last_message_at, last_question
                    )
                    SELECT DISTINCT ON (conversation_id)
                        conversation_id,
                        tenant_id,
                        user_id,
                        CASE WHEN length(question) > 30 THEN substring(question from 1 for 30) || '...' ELSE question END,
                        '',
                        false,
                        false,
                        count(*) OVER (PARTITION BY conversation_id),
                        min(created_at) OVER (PARTITION BY conversation_id),
                        max(created_at) OVER (PARTITION BY conversation_id),
                        max(created_at) OVER (PARTITION BY conversation_id),
                        first_value(question) OVER (
                            PARTITION BY conversation_id ORDER BY created_at DESC
                        )
                    FROM chat_turns
                    ON CONFLICT (id) DO NOTHING
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chat_conversations_tenant_user
                    ON chat_conversations (tenant_id, user_id, last_message_at DESC)
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

    def _conversation_from_row(self, row) -> dict:
        return {
            "id": row[0],
            "conversation_id": row[0],
            "user_id": row[1],
            "tenant_id": row[2],
            "title": row[3],
            "summary": row[4],
            "pinned": row[5],
            "archived": row[6],
            "message_count": row[7],
            "created_at": row[8].isoformat(),
            "updated_at": row[9].isoformat(),
            "last_message_at": row[10].isoformat() if row[10] else None,
            "last_question": row[11],
        }
