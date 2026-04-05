# Transcript-Truth Tool Result Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the runtime `ArtifactStore` hot path with a hard-cutover architecture built on transcript truth, session-local `tool-results/`, and SQLite-backed projections, while explicitly dropping old-session resume compatibility.

**Architecture:** Add three new persistence components: a session-local immutable `ToolResultStore`, a single-writer `ToolCommitCoordinator`, and a projection-only `ProjectionDb`. Move all large-result materialization and replacement persistence out of tool execution and into the query commit path, switch resume/context assembly to transcript-persisted replacement truth, then cut adapter/UI/cleanup over to SQLite projections and delete the legacy `ArtifactStore` runtime dependency before merge.

**Tech Stack:** Python 3.8 standard library (`sqlite3`, `threading`, `json`, `os`, `io`, `tempfile`, `unittest`), existing `QueryEngine`/`TranscriptStore` architecture, session-local JSONL transcript truth, Windows-safe file IO under Win7 constraints.

---

## File Map

| File | Operation | Responsibility |
|------|-----------|----------------|
| `src/embedagent/persistence_sanitize.py` | **Create** | Shared sanitize helpers moved out of `artifacts.py` so projections and tool-result persistence can reuse them without `ArtifactStore` |
| `src/embedagent/tool_result_store.py` | **Create** | Session-local immutable file store for large tool-result fields keyed by `session_id/tool_call_id/field_name` |
| `src/embedagent/projection_db.py` | **Create** | SQLite projection schema, reads, and upserts for artifacts/session summary/project-memory views |
| `src/embedagent/tool_commit.py` | **Create** | Single-writer commit coordinator that materializes large fields, appends transcript replacement events, updates in-memory session, and refreshes projections |
| `src/embedagent/tools/_base.py` | **Modify** | Remove runtime artifact writes from `ToolContext`; keep only pure preview/size helpers and constants |
| `src/embedagent/tools/runtime.py` | **Modify** | Return raw observations from tools; stop calling `shrink_observation()` in the execution path |
| `src/embedagent/query_engine.py` | **Modify** | Replace direct observation persistence with serial commit coordination after tool execution |
| `src/embedagent/session.py` | **Modify** | Track stored-path references and replacement metadata without `_artifact_ref` assumptions |
| `src/embedagent/context.py` | **Modify** | Consume transcript-persisted `content_replacement` records as prompt truth; remove `_artifact_ref`-based replacement reconstruction |
| `src/embedagent/transcript_store.py` | **Modify** | Ensure `content_replacement` payloads are appended and loaded with the final stored-path/replacement-text schema |
| `src/embedagent/session_restore.py` | **Modify** | Restore replacement state from transcript exactly; reject transcript-missing or old-format resume paths |
| `src/embedagent/session_store.py` | **Modify** | Use `ProjectionDb` for session projection data and optional `summary.json` export; stop depending on mutable JSON indexes |
| `src/embedagent/project_memory.py` | **Modify** | Write/read recipe and issue projections through SQLite instead of JSON files |
| `src/embedagent/memory_maintenance.py` | **Modify** | Cleanup session-local `tool-results/` based on transcript/SQLite truth, not `ArtifactStore` |
| `src/embedagent/inprocess_adapter.py` | **Modify** | Switch `/artifacts` API to SQLite-backed projections and remove summary-based degraded resume fallback |
| `src/embedagent/artifacts.py` | **Delete** | Remove the legacy shared-index runtime implementation from the merged final state |
| `tests/test_tool_result_store.py` | **Create** | Verify session-local write-if-absent behavior, preview metadata, and Windows-safe directory handling |
| `tests/test_projection_db.py` | **Create** | Verify schema creation, upserts, listings, and rebuild-safe reads from SQLite |
| `tests/test_tool_commit.py` | **Create** | Verify single-writer commit behavior, replacement persistence, and projection-failure isolation |
| `tests/test_query_engine_refactor.py` | **Modify** | Extend coverage for raw observation execution, serial commit, replacement replay, and parallel read-file safety |
| `tests/test_inprocess_adapter_frontend_api.py` | **Modify** | Cover SQLite-backed artifact listing/reading and hard-fail resume semantics |
| `docs/query-context-redesign.md` | **Modify** | Update design notes to reflect transcript-truth tool-result cutover and SQLite projections |
| `docs/development-tracker.md` | **Modify** | Mark cutover implementation progress and validation milestones |
| `docs/design-change-log.md` | **Modify** | Record that the cutover removed `ArtifactStore` truth dependency |

---

### Task 1: Create the New Persistence Foundation

**Files:**
- Create: `src/embedagent/persistence_sanitize.py`
- Create: `src/embedagent/tool_result_store.py`
- Create: `src/embedagent/projection_db.py`
- Create: `tests/test_tool_result_store.py`
- Create: `tests/test_projection_db.py`

- [ ] **Step 1: Write the failing storage tests first**

Create `tests/test_tool_result_store.py` with this initial content:

```python
import os
import shutil
import tempfile
import unittest

from embedagent.tool_result_store import ToolResultStore


class TestToolResultStore(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-tool-results-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.store = ToolResultStore(self.workspace)

    def test_write_text_field_is_session_local_and_write_once(self):
        first = self.store.write_text(
            session_id="s-1",
            tool_call_id="call-1",
            field_name="content",
            text="hello\nworld",
        )
        second = self.store.write_text(
            session_id="s-1",
            tool_call_id="call-1",
            field_name="content",
            text="DIFFERENT",
        )
        self.assertEqual(first.relative_path, second.relative_path)
        with open(first.absolute_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "hello\nworld")
```

Create `tests/test_projection_db.py` with this initial content:

```python
import os
import shutil
import tempfile
import unittest

from embedagent.projection_db import ProjectionDb


class TestProjectionDb(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-projection-db-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.db = ProjectionDb(os.path.join(self.workspace, ".embedagent", "memory", "projections.sqlite3"))

    def test_schema_bootstrap_and_session_projection_upsert(self):
        self.db.initialize()
        self.db.upsert_session_projection(
            session_id="session-1",
            updated_at="2026-04-05T00:00:00Z",
            current_mode="explore",
            turn_count=1,
            message_count=2,
            last_transition_reason="completed",
            last_transition_message="ok",
            summary_text="demo",
        )
        row = self.db.get_session_projection("session-1")
        self.assertIsNotNone(row)
        self.assertEqual(row["current_mode"], "explore")
```

- [ ] **Step 2: Run the new tests and verify they fail because the persistence modules do not exist yet**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_tool_result_store tests.test_projection_db -v
```

Expected:

```text
ERROR: Failed to import test module 'tests.test_tool_result_store'
ModuleNotFoundError: No module named 'embedagent.tool_result_store'
```

- [ ] **Step 3: Implement shared sanitize helpers**

Create `src/embedagent/persistence_sanitize.py`:

```python
from __future__ import annotations

import re


_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{12,}")
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)


def sanitize_text(text):
    value = str(text or "")
    value = _OPENAI_KEY_RE.sub("<redacted-openai-key>", value)
    value = _BEARER_RE.sub("Bearer <redacted>", value)
    return value


def sanitize_jsonable(value):
    if isinstance(value, dict):
        return dict((key, sanitize_jsonable(item)) for key, item in value.items())
    if isinstance(value, list):
        return [sanitize_jsonable(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value
```

- [ ] **Step 4: Implement the immutable session-local tool result store**

Create `src/embedagent/tool_result_store.py`:

```python
from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass

from embedagent.persistence_sanitize import sanitize_jsonable, sanitize_text


@dataclass
class StoredToolResultField:
    session_id: str
    tool_call_id: str
    field_name: str
    content_kind: str
    absolute_path: str
    relative_path: str
    byte_count: int
    line_count: int
    preview_text: str


class ToolResultStore(object):
    def __init__(self, workspace, relative_root=".embedagent/memory/sessions"):
        self.workspace = os.path.realpath(workspace)
        self.root = os.path.join(self.workspace, *relative_root.replace("\\", "/").split("/"))

    def _preview(self, text, limit=1600):
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...[stored preview truncated]"

    def _field_path(self, session_id, tool_call_id, field_name, extension):
        return os.path.join(self.root, session_id, "tool-results", tool_call_id, "%s.%s" % (field_name, extension))

    def _ensure_parent(self, path):
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)

    def _write_if_absent(self, path, text):
        self._ensure_parent(path)
        try:
            with io.open(path, "x", encoding="utf-8", newline="") as handle:
                handle.write(text)
        except FileExistsError:
            pass

    def write_text(self, session_id, tool_call_id, field_name, text):
        sanitized = sanitize_text(text)
        path = self._field_path(session_id, tool_call_id, field_name, "txt")
        self._write_if_absent(path, sanitized)
        return StoredToolResultField(
            session_id, tool_call_id, field_name, "text", path,
            os.path.relpath(path, self.workspace).replace(os.sep, "/"),
            len(sanitized.encode("utf-8")),
            sanitized.count("\n") + (1 if sanitized else 0),
            self._preview(sanitized),
        )

    def write_json(self, session_id, tool_call_id, field_name, value):
        serialized = json.dumps(sanitize_jsonable(value), ensure_ascii=False, indent=2, sort_keys=True)
        path = self._field_path(session_id, tool_call_id, field_name, "json")
        self._write_if_absent(path, serialized)
        return StoredToolResultField(
            session_id, tool_call_id, field_name, "json", path,
            os.path.relpath(path, self.workspace).replace(os.sep, "/"),
            len(serialized.encode("utf-8")),
            serialized.count("\n") + (1 if serialized else 0),
            self._preview(serialized),
        )
```

- [ ] **Step 5: Implement the projection DB schema and read/write methods**

Create `src/embedagent/projection_db.py`:

```python
from __future__ import annotations

import os
import sqlite3
import threading


class ProjectionDb(object):
    def __init__(self, db_path):
        self.db_path = os.path.realpath(db_path)
        self._lock = threading.Lock()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with self._lock:
            connection = self._connect()
            try:
                connection.executescript(
                    '''
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
                    '''
                )
                connection.commit()
            finally:
                connection.close()
```

Then add these methods:

```python
    def upsert_session_projection(self, **payload):
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    '''
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
                    ''',
                    (
                        payload["session_id"], payload["updated_at"], payload["current_mode"],
                        payload["turn_count"], payload["message_count"],
                        payload.get("last_transition_reason"), payload.get("last_transition_message"),
                        payload.get("summary_text"),
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def get_session_projection(self, session_id):
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute("SELECT * FROM session_projection WHERE session_id = ?", (session_id,)).fetchone()
                return dict(row) if row is not None else None
            finally:
                connection.close()

    def upsert_tool_result_projection(self, **payload):
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    '''
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
                    ''',
                    (
                        payload["session_id"], payload["tool_call_id"], payload["message_id"],
                        payload["tool_name"], payload["field_name"], payload["stored_path"],
                        payload["preview_text"], payload["byte_count"], payload.get("line_count"),
                        payload["content_kind"], payload["created_at"],
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def list_tool_results(self, limit=20):
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
```

- [ ] **Step 6: Run the new storage tests and verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_tool_result_store tests.test_projection_db -v
```

Expected:

```text
OK
```

- [ ] **Step 7: Commit the persistence foundation**

Run:

```bash
git add src/embedagent/persistence_sanitize.py src/embedagent/tool_result_store.py src/embedagent/projection_db.py tests/test_tool_result_store.py tests/test_projection_db.py
git commit -m "refactor: add transcript cutover persistence foundation"
```

---

### Task 2: Build the Single-Writer Commit Coordinator

**Files:**
- Create: `src/embedagent/tool_commit.py`
- Create: `tests/test_tool_commit.py`
- Modify: `src/embedagent/session.py`
- Modify: `src/embedagent/transcript_store.py`

- [ ] **Step 1: Write failing commit-coordinator tests**

Create `tests/test_tool_commit.py` with this initial content:

```python
import shutil
import tempfile
import unittest

from embedagent.projection_db import ProjectionDb
from embedagent.session import Action, Observation, Session
from embedagent.tool_commit import ToolCommitCoordinator
from embedagent.tool_result_store import ToolResultStore
from embedagent.transcript_store import TranscriptStore


class TestToolCommitCoordinator(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-tool-commit-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.store = ToolResultStore(self.workspace)
        self.db = ProjectionDb(self.workspace + "/.embedagent/memory/projections.sqlite3")
        self.transcript = TranscriptStore(self.workspace)
        self.coordinator = ToolCommitCoordinator(self.store, self.db, self.transcript)
        self.session = Session()
        self.session.add_user_message("inspect file", turn_id="t-1", message_id="m-user")
        self.session.begin_step(step_id="s-1")

    def test_large_content_creates_stored_path_and_replacement_record(self):
        action = Action("read_file", {"path": "src/demo.c"}, "call-1")
        observation = Observation("read_file", True, None, {"path": "src/demo.c", "content": "x" * 5000})
        committed = self.coordinator.commit(self.session, action, observation, current_mode="explore")
        self.assertTrue(committed.success)
        self.assertIn("content_stored_path", committed.data)
        self.assertEqual(len(self.session.content_replacements), 1)
```

- [ ] **Step 2: Run the commit tests and confirm they fail because `ToolCommitCoordinator` does not exist yet**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_tool_commit -v
```

Expected:

```text
ERROR: Failed to import test module 'tests.test_tool_commit'
ModuleNotFoundError: No module named 'embedagent.tool_commit'
```

- [ ] **Step 3: Implement the commit coordinator**

Create `src/embedagent/tool_commit.py`:

```python
from __future__ import annotations

import threading
import time
from copy import deepcopy

from embedagent.session import Observation


class ToolCommitCoordinator(object):
    def __init__(self, tool_result_store, projection_db, transcript_store):
        self._tool_result_store = tool_result_store
        self._projection_db = projection_db
        self._transcript_store = transcript_store
        self._lock = threading.Lock()
        self._inline_text_limit = 1600

    def _materialize_text(self, session, action, data, field_name):
        value = data.get(field_name)
        if not isinstance(value, str) or len(value) <= self._inline_text_limit:
            return None
        stored = self._tool_result_store.write_text(session.session_id, action.call_id, field_name, value)
        data[field_name + "_stored_path"] = stored.relative_path
        data[field_name + "_preview"] = stored.preview_text
        data[field_name] = stored.preview_text
        return {
            "field_name": field_name,
            "stored_path": stored.relative_path,
            "replacement_text": "Tool result replaced: %s %s -> %s" % (
                action.name,
                data.get("path") or action.arguments.get("path") or "",
                stored.relative_path,
            ),
        }
```

Then complete the `commit(...)` method:

```python
    def commit(self, session, action, raw_observation, current_mode):
        with self._lock:
            data = deepcopy(raw_observation.data) if isinstance(raw_observation.data, dict) else raw_observation.data
            committed = Observation(raw_observation.tool_name, raw_observation.success, raw_observation.error, data)
            replacements = []
            if isinstance(committed.data, dict):
                for field_name in ("content", "stdout", "stderr", "diff"):
                    item = self._materialize_text(session, action, committed.data, field_name)
                    if item is not None:
                        replacements.append(item)
            finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._transcript_store.append_event(
                session.session_id,
                "tool_result",
                {
                    "turn_id": session.turns[-1].turn_id if session.turns else "",
                    "step_id": session.current_step().step_id if session.current_step() is not None else "",
                    "call_id": action.call_id,
                    "tool_name": action.name,
                    "finished_at": finished_at,
                    "observation": committed.to_dict(),
                },
            )
            if replacements:
                payload = {
                    "message_id": "",
                    "tool_call_id": action.call_id,
                    "tool_name": action.name,
                    "replacements": replacements,
                }
                self._transcript_store.append_event(session.session_id, "content_replacement", payload)
                session.record_content_replacement(payload)
                for item in replacements:
                    try:
                        self._projection_db.upsert_tool_result_projection(
                            session_id=session.session_id,
                            tool_call_id=action.call_id,
                            message_id="",
                            tool_name=action.name,
                            field_name=item["field_name"],
                            stored_path=item["stored_path"],
                            preview_text=committed.data.get(item["field_name"] + "_preview", ""),
                            byte_count=len(committed.data.get(item["field_name"] + "_preview", "").encode("utf-8")),
                            line_count=committed.data.get(item["field_name"] + "_preview", "").count("\n") + 1,
                            content_kind="text",
                            created_at=finished_at,
                        )
                    except Exception:
                        pass
            return committed
```

- [ ] **Step 4: Update session replacement/reference handling**

Modify `src/embedagent/session.py`:

```python
    def _stored_refs_from_observation(self, observation):
        if not isinstance(observation.data, dict):
            return []
        refs = []
        for key, value in observation.data.items():
            if key.endswith("_stored_path") and value:
                refs.append(str(value))
        return refs[:8]
```

Then update `add_observation(...)` so `replaced_by_refs` defaults to `_stored_refs_from_observation(observation)` instead of `_artifact_refs_from_observation(observation)`.

- [ ] **Step 5: Run the commit tests and verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_tool_commit -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit the commit-layer foundation**

Run:

```bash
git add src/embedagent/tool_commit.py src/embedagent/session.py tests/test_tool_commit.py
git commit -m "refactor: add single-writer tool commit coordinator"
```

---

### Task 3: Cut Tool Execution Over To Raw Observations And Serial Commit

**Files:**
- Modify: `src/embedagent/tools/_base.py`
- Modify: `src/embedagent/tools/runtime.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_query_engine_refactor.py`

- [ ] **Step 1: Add a failing regression that proves `ToolRuntime` no longer writes during execution**

Append this test to `tests/test_query_engine_refactor.py`:

```python
    def test_read_file_execution_returns_raw_observation_without_stored_path(self):
        workspace = self.make_workspace({"src/demo.c": "x" * 5000})
        runtime = ToolRuntime(workspace)
        result = runtime.execute("read_file", {"path": "src/demo.c"})
        self.assertTrue(result.success)
        self.assertIn("content", result.data)
        self.assertNotIn("content_stored_path", result.data)
```

- [ ] **Step 2: Run the focused regression and confirm it fails because execution still shrinks/writes in the runtime path**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_query_engine_refactor.TestQueryEngineRefactor.test_read_file_execution_returns_raw_observation_without_stored_path -v
```

Expected:

```text
FAIL: test_read_file_execution_returns_raw_observation_without_stored_path
```

- [ ] **Step 3: Remove artifact writes from the execution layer**

Modify `src/embedagent/tools/_base.py` so `ToolContext` no longer owns artifact persistence:

```python
class ToolContext(object):
    def __init__(self, workspace, app_config=None):
        self.workspace = workspace
        self.app_config = app_config
        self._thread_local = threading.local()

    def preview_text(self, text, limit):
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...[stored preview truncated]"
```

Delete the runtime persistence helpers:

- `shrink_text_field`
- `shrink_list_field`
- `shrink_observation`
- `artifact_store` constructor dependency

Keep only pure constants and preview helpers that the commit layer can reuse.

- [ ] **Step 4: Return raw observations from `ToolRuntime` and route persistence through `ToolCommitCoordinator`**

Modify `src/embedagent/tools/runtime.py`:

```python
    def __init__(self, workspace: str, app_config=None) -> None:
        self.workspace = os.path.realpath(workspace)
        self.tool_result_store = ToolResultStore(self.workspace)
        self.projection_db = ProjectionDb(os.path.join(self.workspace, ".embedagent", "memory", "projections.sqlite3"))
        self._ctx = ToolContext(self.workspace, app_config=app_config)
```

Replace:

```python
observation = self._ctx.shrink_observation(tool.handler(arguments))
```

with:

```python
observation = tool.handler(arguments)
```

Modify `src/embedagent/query_engine.py`:

```python
from embedagent.tool_commit import ToolCommitCoordinator

        self.memory_maintenance = memory_maintenance or MemoryMaintenance(
            summary_store=self.summary_store,
            project_memory_store=self.project_memory_store,
            tool_result_store=self.tools.tool_result_store,
            projection_db=self.tools.projection_db,
        )
        self.tool_commit = ToolCommitCoordinator(
            self.tools.tool_result_store,
            self.tools.projection_db,
            self.transcript_store,
        )
```

Then in `_record_tool_observation(...)` call `self.tool_commit.commit(...)` before `session.add_observation(...)` and before `_persist_summary(...)`.

- [ ] **Step 5: Add and run a focused regression proving projection failures do not flip tool success**

Append this test to `tests/test_query_engine_refactor.py`:

```python
    def test_projection_failure_does_not_flip_tool_success(self):
        workspace = self.make_workspace({"src/demo.c": "x" * 5000})
        runtime = ToolRuntime(workspace)
        runtime.projection_db.upsert_tool_result_projection = lambda **_: (_ for _ in ()).throw(RuntimeError("db down"))
        engine = self.make_query_engine(tools=runtime)
        result = engine.submit_turn("read src/demo.c", stream=False, session=Session())
        last_observation = result.session.turns[-1].observations[-1]
        self.assertTrue(last_observation.success)
```

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_query_engine_refactor -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit the raw-execution and serial-commit cut**

Run:

```bash
git add src/embedagent/tools/_base.py src/embedagent/tools/runtime.py src/embedagent/query_engine.py tests/test_query_engine_refactor.py
git commit -m "refactor: split raw tool execution from serial commit"
```

---

### Task 4: Cut Context And Resume Over To Transcript-Persisted Replacement Truth

**Files:**
- Modify: `src/embedagent/context.py`
- Modify: `src/embedagent/session_restore.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `tests/test_query_engine_refactor.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Write failing regressions for replacement replay and hard-fail resume**

Append to `tests/test_query_engine_refactor.py`:

```python
    def test_context_manager_uses_persisted_replacement_text_without_regeneration(self):
        session = Session()
        session.add_user_message("show file", turn_id="t-1", message_id="m-1")
        session.begin_step(step_id="s-1")
        session.record_content_replacement(
            {
                "message_id": "m-tool",
                "tool_call_id": "call-1",
                "tool_name": "read_file",
                "replacements": [
                    {
                        "field_name": "content",
                        "stored_path": ".embedagent/memory/sessions/s/tool-results/call-1/content.txt",
                        "replacement_text": "PERSISTED REPLACEMENT TEXT",
                    }
                ],
            }
        )
        manager = ContextManager(project_memory=ProjectMemoryStore(self.workspace))
        rendered = manager.build_messages(session, "explore").messages
        self.assertIn("PERSISTED REPLACEMENT TEXT", json.dumps(rendered, ensure_ascii=False))
```

Append to `tests/test_inprocess_adapter_frontend_api.py`:

```python
    def test_resume_session_requires_transcript(self):
        with self.assertRaises(ValueError):
            self.adapter.resume_session("missing-session")
```

- [ ] **Step 2: Run the focused tests and confirm they fail because context still reconstructs replacements dynamically and adapter still degrades**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_query_engine_refactor tests.test_inprocess_adapter_frontend_api -v
```

Expected:

```text
FAIL: persisted replacement text not found
FAIL: ValueError not raised
```

- [ ] **Step 3: Make `ContextManager` use transcript replacement truth directly**

Modify `src/embedagent/context.py` so replacement rendering reads `session.content_replacements` directly:

```python
def _replacement_map(session):
    mapping = {}
    for payload in session.content_replacements:
        tool_call_id = str(payload.get("tool_call_id") or "")
        for item in payload.get("replacements") or []:
            mapping[(tool_call_id, str(item.get("field_name") or ""))] = str(item.get("replacement_text") or "")
    return mapping
```

Then update the tool-message compaction path so it:

- looks up `(tool_call_id, field_name)` in that mapping
- uses the persisted `replacement_text` when present
- does **not** regenerate replacement text from `stored_path`
- removes all `_artifact_ref` suffix scans from the final merged code path

- [ ] **Step 4: Remove degraded summary-based resume fallback**

Modify `src/embedagent/inprocess_adapter.py`:

```python
    def resume_session(self, reference):
        transcript_path = self.summary_store.resolve_transcript_path(reference)
        if not os.path.isfile(transcript_path):
            raise ValueError("Transcript 不存在，旧格式 session 不再支持恢复：%s" % reference)
        events = self.transcript_store.load_events(transcript_path)
        restored = self.session_restorer.restore(events)
        current_mode = require_mode(mode or restored.current_mode or DEFAULT_MODE)["slug"]
        state = ManagedSession(session=restored.session, current_mode=current_mode)
        with self._lock:
            self._sessions[restored.session.session_id] = state
        return self.get_session_snapshot(restored.session.session_id)
```

Delete the branch that:

- synthesizes an empty session
- marks `timeline_replay_status = "degraded"`
- falls back to summary-only resume

Modify `src/embedagent/session_restore.py` so transcript replay rejects missing or malformed truth inputs immediately instead of silently degrading.

- [ ] **Step 5: Run the focused tests and verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_query_engine_refactor tests.test_inprocess_adapter_frontend_api -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit the replacement/resume cut**

Run:

```bash
git add src/embedagent/context.py src/embedagent/session_restore.py src/embedagent/inprocess_adapter.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "refactor: use transcript replacement truth and hard-fail old resume paths"
```

---

### Task 5: Replace Projection Consumers, Artifact APIs, And Cleanup With SQLite

**Files:**
- Modify: `src/embedagent/session_store.py`
- Modify: `src/embedagent/project_memory.py`
- Modify: `src/embedagent/memory_maintenance.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `tests/test_projection_db.py`
- Modify: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Write failing tests for SQLite-backed artifact listing and cleanup safety**

Append to `tests/test_inprocess_adapter_frontend_api.py`:

```python
    def test_list_artifacts_reads_from_projection_db(self):
        self.adapter.tools.projection_db.upsert_tool_result_projection(
            session_id="session-1",
            tool_call_id="call-1",
            message_id="m-1",
            tool_name="read_file",
            field_name="content",
            stored_path=".embedagent/memory/sessions/session-1/tool-results/call-1/content.txt",
            preview_text="preview",
            byte_count=7,
            line_count=1,
            content_kind="text",
            created_at="2026-04-05T00:00:00Z",
        )
        items = self.adapter.list_artifacts(limit=10)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["path"], ".embedagent/memory/sessions/session-1/tool-results/call-1/content.txt")
```

Append to `tests/test_projection_db.py`:

```python
    def test_delete_and_rebuild_projection_db(self):
        self.db.initialize()
        os.remove(self.db.db_path)
        self.db.initialize()
        self.assertTrue(os.path.isfile(self.db.db_path))
```

- [ ] **Step 2: Run the projection-facing tests and confirm they fail because adapter and cleanup still use the legacy stores**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_projection_db tests.test_inprocess_adapter_frontend_api -v
```

Expected:

```text
FAIL: list_artifacts returned [] or used legacy ArtifactStore path
```

- [ ] **Step 3: Switch the adapter’s public artifact APIs to SQLite-backed projections**

Modify `src/embedagent/inprocess_adapter.py`:

```python
    def list_artifacts(self, limit=20):
        items = self.tools.projection_db.list_tool_results(limit=limit)
        result = []
        for item in items:
            result.append(
                {
                    "path": item["stored_path"],
                    "tool_name": item["tool_name"],
                    "field_name": item["field_name"],
                    "created_at": item["created_at"],
                    "preview_text": item["preview_text"],
                    "byte_count": item["byte_count"],
                }
            )
        return result

    def read_artifact(self, reference):
        absolute_path = self.tools.tool_result_store.resolve_existing_path(reference)
        with open(absolute_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        return {"path": reference, "content": content}
```

Keep the public shape (`path`, `tool_name`, `field_name`) stable so GUI/TUI avoid unnecessary UI churn while the backend truth changes completely.

- [ ] **Step 4: Move session/project-memory projections to SQLite and rewrite cleanup**

Modify `src/embedagent/session_store.py`:

```python
    def persist(self, session, current_mode, context_result=None):
        payload = self._build_payload(session, current_mode, context_result)
        self.projection_db.upsert_session_projection(
            session_id=payload["session_id"],
            updated_at=payload["updated_at"],
            current_mode=payload["current_mode"],
            turn_count=payload["turn_count"],
            message_count=payload["message_count"],
            last_transition_reason=payload.get("last_transition_reason"),
            last_transition_message=payload.get("last_transition_message"),
            summary_text=payload.get("summary_text", ""),
        )
        self._write_optional_summary_json(payload)
        return os.path.join(self.relative_root, session.session_id, "summary.json").replace(os.sep, "/")
```

Modify `src/embedagent/project_memory.py` so recipes and issues are written through `ProjectionDb` methods instead of JSON files.

Modify `src/embedagent/memory_maintenance.py`:

```python
    def run(self):
        active_paths = set(self.summary_store.collect_stored_paths())
        active_paths.update(self.project_memory_store.collect_stored_paths())
        return self.tool_result_store.cleanup_unreferenced(active_paths)
```

- [ ] **Step 5: Run the projection/API tests and verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_projection_db tests.test_inprocess_adapter_frontend_api -v
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit the SQLite projection cut**

Run:

```bash
git add src/embedagent/session_store.py src/embedagent/project_memory.py src/embedagent/memory_maintenance.py src/embedagent/inprocess_adapter.py tests/test_projection_db.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "refactor: switch artifact and projection consumers to sqlite"
```

---

### Task 6: Delete The Legacy ArtifactStore Path And Finish Verification

**Files:**
- Delete: `src/embedagent/artifacts.py`
- Modify: `src/embedagent/query_engine.py`
- Modify: `docs/query-context-redesign.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`

- [ ] **Step 1: Add a failing guard test that ensures the legacy artifact module is no longer imported by the runtime hot path**

Append this regression to `tests/test_query_engine_refactor.py`:

```python
    def test_runtime_no_longer_depends_on_artifact_store(self):
        runtime = ToolRuntime(self.workspace)
        self.assertFalse(hasattr(runtime, "artifact_store"))
```

- [ ] **Step 2: Run the full focused test slice and confirm the guard fails before deleting the legacy path**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_tool_result_store tests.test_projection_db tests.test_tool_commit tests.test_query_engine_refactor tests.test_inprocess_adapter_frontend_api -v
```

Expected:

```text
FAIL: runtime still exposes artifact_store
```

- [ ] **Step 3: Delete `ArtifactStore` and remove the final imports/usages**

Delete `src/embedagent/artifacts.py`.

Then remove every remaining import of `ArtifactStore` and replace it with:

- `ProjectionDb`
- `ToolResultStore`
- `persistence_sanitize`

The final runtime code must not import `embedagent.artifacts` anywhere outside deleted or fully dead code paths.

- [ ] **Step 4: Update the architectural documents to match the merged final state**

Modify `docs/query-context-redesign.md` so the persistence section says:

```markdown
- Session truth remains `.embedagent/memory/sessions/<session_id>/transcript.jsonl`
- Large tool-result fields are now materialized under `.embedagent/memory/sessions/<session_id>/tool-results/<tool_call_id>/<field>.txt|json`
- SQLite projections under `.embedagent/memory/projections.sqlite3` back artifact browsing, session summary listing, and project-memory read models
- `ArtifactStore.index.json` is no longer part of the runtime hot path
```

Also update:

- `docs/development-tracker.md`
- `docs/design-change-log.md`

to record the hard cutover as implemented, not just planned.

- [ ] **Step 5: Run the final verification suite**

Run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_tool_result_store tests.test_projection_db tests.test_tool_commit tests.test_query_engine_refactor tests.test_inprocess_adapter_frontend_api -v
.venv\Scripts\python.exe scripts\validate-phase5.py
.venv\Scripts\python.exe scripts\validate-phase6.py
```

Expected:

```text
All selected unittest modules pass
validate-phase5.py exits 0
validate-phase6.py exits 0
```

- [ ] **Step 6: Commit the final cutover**

Run:

```bash
git add docs/query-context-redesign.md docs/development-tracker.md docs/design-change-log.md src/embedagent tests
git commit -m "refactor: cut over to transcript truth tool result persistence"
```

---

## Self-Review Checklist

- [ ] Every runtime path that used `ArtifactStore.index.json` now points at transcript truth or SQLite projections
- [ ] No prompt-facing logic regenerates replacement text from stored paths
- [ ] No resume path survives without transcript truth
- [ ] No merged file still relies on `_artifact_ref` as a truth-bearing suffix convention
- [ ] Projection failures are contained and logged, not surfaced as tool failure
- [ ] The final branch deletes `src/embedagent/artifacts.py`
