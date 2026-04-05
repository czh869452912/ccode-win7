from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


class ProjectionDb(object):
    def __init__(self, db_path: str) -> None:
        self.db_path = os.path.realpath(db_path)
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with self._lock:
            connection = self._connect()
            try:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS schema_meta (
                      key TEXT PRIMARY KEY,
                      value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS session_projection (
                      session_id TEXT PRIMARY KEY,
                      updated_at TEXT NOT NULL,
                      current_mode TEXT NOT NULL,
                      started_at TEXT,
                      turn_count INTEGER NOT NULL,
                      message_count INTEGER NOT NULL,
                      user_goal TEXT,
                      transcript_ref TEXT,
                      summary_ref TEXT,
                      last_transition_reason TEXT,
                      last_transition_message TEXT,
                      summary_text TEXT
                    );
                    CREATE TABLE IF NOT EXISTS tool_result_projection (
                      session_id TEXT NOT NULL,
                      tool_call_id TEXT NOT NULL,
                      message_id TEXT NOT NULL,
                      tool_name TEXT NOT NULL,
                      field_name TEXT NOT NULL,
                      stored_path TEXT NOT NULL,
                      preview_text TEXT NOT NULL,
                      byte_count INTEGER NOT NULL,
                      line_count INTEGER,
                      content_kind TEXT NOT NULL,
                      created_at TEXT NOT NULL,
                      PRIMARY KEY (session_id, tool_call_id, field_name)
                    );
                    """
                )
                self._ensure_columns(
                    connection,
                    "session_projection",
                    {
                        "started_at": "TEXT",
                        "user_goal": "TEXT",
                        "transcript_ref": "TEXT",
                        "summary_ref": "TEXT",
                    },
                )
                connection.commit()
            finally:
                connection.close()

    def _ensure_columns(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        columns: Dict[str, str],
    ) -> None:
        existing = set()
        for row in connection.execute("PRAGMA table_info(%s)" % table_name).fetchall():
            name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
            existing.add(str(name))
        for column_name, ddl in columns.items():
            if column_name in existing:
                continue
            connection.execute(
                "ALTER TABLE %s ADD COLUMN %s %s"
                % (table_name, column_name, ddl)
            )

    def upsert_session_projection(self, **payload: Any) -> None:
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO session_projection (
                      session_id, updated_at, current_mode, started_at, turn_count, message_count,
                      user_goal, transcript_ref, summary_ref,
                      last_transition_reason, last_transition_message, summary_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                      updated_at=excluded.updated_at,
                      current_mode=excluded.current_mode,
                      started_at=excluded.started_at,
                      turn_count=excluded.turn_count,
                      message_count=excluded.message_count,
                      user_goal=excluded.user_goal,
                      transcript_ref=excluded.transcript_ref,
                      summary_ref=excluded.summary_ref,
                      last_transition_reason=excluded.last_transition_reason,
                      last_transition_message=excluded.last_transition_message,
                      summary_text=excluded.summary_text
                    """,
                    (
                        payload["session_id"],
                        payload["updated_at"],
                        payload["current_mode"],
                        payload.get("started_at"),
                        payload["turn_count"],
                        payload["message_count"],
                        payload.get("user_goal"),
                        payload.get("transcript_ref"),
                        payload.get("summary_ref"),
                        payload.get("last_transition_reason"),
                        payload.get("last_transition_message"),
                        payload.get("summary_text"),
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def get_session_projection(self, session_id: str) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT * FROM session_projection WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                return dict(row) if row is not None else None
            finally:
                connection.close()

    def list_session_projections(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    "SELECT * FROM session_projection ORDER BY updated_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                connection.close()

    def delete_session_projections_except(self, session_ids: List[str]) -> None:
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                keep = [str(item) for item in session_ids or [] if str(item)]
                if keep:
                    placeholders = ", ".join(["?"] * len(keep))
                    connection.execute(
                        "DELETE FROM session_projection WHERE session_id NOT IN (%s)" % placeholders,
                        tuple(keep),
                    )
                else:
                    connection.execute("DELETE FROM session_projection")
                connection.commit()
            finally:
                connection.close()

    def upsert_tool_result_projection(self, **payload: Any) -> None:
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO tool_result_projection (
                      session_id, tool_call_id, message_id, tool_name, field_name,
                      stored_path, preview_text, byte_count, line_count, content_kind, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, tool_call_id, field_name) DO UPDATE SET
                      message_id=excluded.message_id,
                      tool_name=excluded.tool_name,
                      stored_path=excluded.stored_path,
                      preview_text=excluded.preview_text,
                      byte_count=excluded.byte_count,
                      line_count=excluded.line_count,
                      content_kind=excluded.content_kind,
                      created_at=excluded.created_at
                    """,
                    (
                        payload["session_id"],
                        payload["tool_call_id"],
                        payload["message_id"],
                        payload["tool_name"],
                        payload["field_name"],
                        payload["stored_path"],
                        payload["preview_text"],
                        payload["byte_count"],
                        payload.get("line_count"),
                        payload["content_kind"],
                        payload["created_at"],
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def list_tool_results(self, limit: int = 20) -> List[Dict[str, Any]]:
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    "SELECT * FROM tool_result_projection ORDER BY created_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                connection.close()
