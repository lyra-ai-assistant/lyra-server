import uuid
import time
from threading import Lock
from typing import Optional

from lyra.db.connection import get_connection, init_db

SESSION_TTL = 1800  # seconds of inactivity before a session expires


class SessionManager:
    def __init__(self):
        self._lock = Lock()
        init_db()

    def get_or_create(self, session_id: Optional[str]) -> tuple[str, list]:
        if session_id and self._is_valid(session_id):
            return session_id, self._get_history(session_id)
        new_id = self._create()
        return new_id, []

    def add_messages(self, session_id: str, user_text: str, assistant_text: str):
        now = time.time()
        with self._lock:
            conn = get_connection()
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, "user", user_text, now),
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, "assistant", assistant_text, now),
            )
            conn.execute(
                "UPDATE sessions SET last_active = ? WHERE id = ?",
                (now, session_id),
            )
            conn.commit()
            conn.close()

    def clear(self, session_id: str):
        with self._lock:
            conn = get_connection()
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            conn.close()

    def active_count(self) -> int:
        cutoff = time.time() - SESSION_TTL
        conn = get_connection()
        row = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE last_active > ?", (cutoff,)
        ).fetchone()
        conn.close()
        return row[0]

    # -- private --

    def _create(self) -> str:
        session_id = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            conn = get_connection()
            conn.execute(
                "INSERT INTO sessions (id, created_at, last_active) VALUES (?, ?, ?)",
                (session_id, now, now),
            )
            conn.commit()
            conn.close()
        return session_id

    def _is_valid(self, session_id: str) -> bool:
        conn = get_connection()
        row = conn.execute(
            "SELECT last_active FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        conn.close()
        if not row:
            return False
        if time.time() - row["last_active"] > SESSION_TTL:
            self.clear(session_id)
            return False
        return True

    def _get_history(self, session_id: str) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"]} for r in rows]


session_manager = SessionManager()
