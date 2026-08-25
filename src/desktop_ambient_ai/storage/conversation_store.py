"""
SQLite-backed conversation session manager.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from ..config import get_default_data_dir


@dataclass
class ConversationSummary:
    id: str
    title: str
    mode: str
    updated_at: str
    message_count: int
    last_snippet: str


@dataclass
class ConversationSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Conversation"
    mode: Literal["quick", "persistent"] = "quick"
    messages: List[dict] = field(default_factory=list)  # list of {"role": str, "content": str, "timestamp": str}
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _store: Optional[ConversationStore] = None

    def add_message(self, role: str, content: str) -> None:
        """Adds a message to the session."""
        now = datetime.now(timezone.utc).isoformat()
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": now
        })
        self.updated_at = now
        if self.mode == "persistent" and self._store:
            self._store.save_session(self)

    def promote_to_persistent(self) -> None:
        """Converts a quick ephemeral session into a persistent conversation."""
        self.mode = "persistent"
        self.title = self._derive_title()
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if self._store:
            self._store.save_session(self)

    def _derive_title(self) -> str:
        """Extracts a short title from the first user prompt."""
        for msg in self.messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                first_line = content.splitlines()[0] if content else ""
                clean = " ".join(first_line.split())
                return clean[:60] if clean else "Untitled Conversation"
        return "Untitled Conversation"


class ConversationStore:
    """Manages SQLite storage for conversations and messages."""

    def __init__(self, db_path: Optional[Path | str] = None):
        if db_path is None:
            data_dir = get_default_data_dir()
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "conversations.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
            """)

    def create_session(self, mode: Literal["quick", "persistent"] = "quick") -> ConversationSession:
        session = ConversationSession(mode=mode, _store=self)
        if mode == "persistent":
            self.save_session(session)
        return session

    def save_session(self, session: ConversationSession) -> None:
        """Persists the session and its messages to SQLite."""
        session._store = self
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO conversations (id, title, mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    mode=excluded.mode,
                    updated_at=excluded.updated_at
            """, (session.id, session.title, session.mode, session.created_at, session.updated_at))

            # Re-sync messages
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (session.id,))
            for msg in session.messages:
                conn.execute("""
                    INSERT INTO messages (conversation_id, role, content, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (session.id, msg["role"], msg["content"], msg.get("timestamp", datetime.now(timezone.utc).isoformat())))

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Loads a session and its message history from SQLite."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return None

            msg_rows = conn.execute(
                "SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (session_id,)
            ).fetchall()

            messages = [
                {"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]}
                for r in msg_rows
            ]

            return ConversationSession(
                id=row["id"],
                title=row["title"],
                mode=row["mode"],
                messages=messages,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                _store=self
            )

    def get_latest_persistent(self) -> Optional[ConversationSession]:
        """Returns the most recently updated persistent conversation."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM conversations WHERE mode = 'persistent' ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            return self.get_session(row["id"])

    def list_persistent(self, limit: int = 20) -> List[ConversationSummary]:
        """Lists persistent conversations for the picker UI."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    c.id, c.title, c.mode, c.updated_at,
                    COUNT(m.id) as message_count,
                    (SELECT content FROM messages WHERE conversation_id = c.id ORDER BY id DESC LIMIT 1) as last_snippet
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.mode = 'persistent'
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [
                ConversationSummary(
                    id=r["id"],
                    title=r["title"],
                    mode=r["mode"],
                    updated_at=r["updated_at"],
                    message_count=r["message_count"],
                    last_snippet=(r["last_snippet"] or "")[:120]
                )
                for r in rows
            ]

    def delete_session(self, session_id: str) -> None:
        """Deletes a session and associated messages."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (session_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (session_id,))
