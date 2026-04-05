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
                      turn_count INTEGER NOT NULL,
                      message_count INTEGER NOT NULL,
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
                connection.commit()
            finally:
                connection.close()

    def upsert_session_projection(self, **payload: Any) -> None:
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO session_projection (
                      session_id, updated_at, current_mode, turn_count, message_count,
                      last_transition_reason, last_transition_message, summary_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                      updated_at=excluded.updated_at,
                      current_mode=excluded.current_mode,
                      turn_count=excluded.turn_count,
                      message_count=excluded.message_count,
                      last_transition_reason=excluded.last_transition_reason,
                      last_transition_message=excluded.last_transition_message,
                      summary_text=excluded.summary_text
                    """,
                    (
                        payload["session_id"],
                        payload["updated_at"],
                        payload["current_mode"],
                        payload["turn_count"],
                        payload["message_count"],
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
