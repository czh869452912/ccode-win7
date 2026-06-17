# GUI Thread Lifecycle Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GUI thread Rename, Fork, and Archive real backend-backed lifecycle actions while keeping GUI state separate from Agent Core session truth.

**Architecture:** Extend the existing session lifecycle boundary instead of teaching the GUI about summary file layout. `SessionSummaryStore` owns summary/projection metadata mutations, `SessionLifecycleManager` and `InProcessAdapter` expose reusable facade methods, `GUIBackend` adds thin routes, and the React app consumes app-shell capabilities plus lifecycle endpoints. Transcript history remains the durable session-history truth; lifecycle metadata stays in summary/projection read models.

**Tech Stack:** Python 3.8, FastAPI route handlers, SQLite projection DB, existing `TranscriptStore`, React plain JS helpers, Node test runner, pytest, ruff.

---

## File Structure

- Modify `src/embedagent/projection_db.py`
  Add additive projection columns and archived filtering support.
- Modify `src/embedagent/session_store.py`
  Add thread metadata helpers plus `rename_session`, `archive_session`, and `fork_session`.
- Modify `src/embedagent/services/session_lifecycle.py`
  Delegate lifecycle operations to `SessionSummaryStore`.
- Modify `src/embedagent/inprocess_adapter.py`
  Expose core facade methods without importing GUI.
- Modify `src/embedagent/frontend/gui/backend/app_shell.py`
  Add `thread_lifecycle` capability metadata.
- Modify `src/embedagent/frontend/gui/backend/server.py`
  Add GUI lifecycle routes and safe error mapping.
- Modify `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
  Normalize `thread_lifecycle` capability.
- Modify `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`
  Prefer `thread.title`, enable actions from app-shell capability, and keep disabled reasons explicit.
- Modify `src/embedagent/frontend/gui/webapp/src/App.jsx`
  Wire sidebar lifecycle actions to API calls and refresh/load sessions.
- Modify `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
  Cover capability normalization.
- Modify `src/embedagent/frontend/gui/webapp/test/app-home-model.test.mjs`
  Cover title precedence and enabled actions.
- Modify `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`
  Add source-contract assertions for lifecycle endpoint wiring.
- Modify `tests/test_session_store.py`
  Cover store-level rename/archive/fork behavior.
- Modify `tests/test_services.py`
  Cover lifecycle manager delegation.
- Modify `tests/test_characterization.py`
  Cover `InProcessAdapter` facade methods.
- Modify `tests/test_gui_backend_api.py`
  Cover GUI lifecycle routes and error mapping.
- Modify active docs in Task 6, then archive this spec/plan under `docs/archive/gui-thread-lifecycle-boundary/`.

## Task 1: Store And Projection Thread Metadata

**Files:**
- Modify: `src/embedagent/projection_db.py`
- Modify: `src/embedagent/session_store.py`
- Test: `tests/test_session_store.py`

- [ ] **Step 1: Write failing store tests**

Append these tests to `tests/test_session_store.py` inside `TestSessionSummaryStore`:

```python
    def test_rename_session_updates_thread_title_and_projection(self):
        store = SessionSummaryStore(self.workspace)
        session = Session()
        session.add_user_message("original goal")
        summary_ref = store.persist(session, "build")

        result = store.rename_session(session.session_id, "  Renamed Thread  ")

        self.assertEqual(result["session_id"], session.session_id)
        self.assertEqual(result["thread"]["title"], "Renamed Thread")
        self.assertEqual(result["title"], "Renamed Thread")
        summary = store.load_summary(summary_ref)
        self.assertEqual(summary["thread"]["title"], "Renamed Thread")
        self.assertEqual(summary["user_goal"], "original goal")
        listed = store.list_summaries(limit=5)
        self.assertEqual(listed[0]["title"], "Renamed Thread")
        self.assertEqual(listed[0]["thread"]["title"], "Renamed Thread")

    def test_rename_session_rejects_empty_title(self):
        store = SessionSummaryStore(self.workspace)
        session = Session()
        session.add_user_message("original goal")
        store.persist(session, "build")

        with self.assertRaises(ValueError) as raised:
            store.rename_session(session.session_id, "   ")

        self.assertEqual(str(raised.exception), "invalid_thread_title")

    def test_archive_session_hides_from_default_list_but_keeps_explicit_listing(self):
        store = SessionSummaryStore(self.workspace)
        session = Session()
        session.add_user_message("archive me")
        store.persist(session, "build")

        archived = store.archive_session(session.session_id)

        self.assertTrue(archived["thread"]["archived"])
        self.assertTrue(archived["thread"]["archived_at"])
        self.assertEqual(store.list_summaries(limit=5), [])
        with_archived = store.list_summaries(limit=5, include_archived=True)
        self.assertEqual(len(with_archived), 1)
        self.assertEqual(with_archived[0]["session_id"], session.session_id)
        self.assertTrue(with_archived[0]["thread"]["archived"])

    def test_cleanup_keeps_archived_sessions(self):
        store = SessionSummaryStore(self.workspace)
        archived_session = Session()
        archived_session.add_user_message("archived")
        active_session = Session()
        active_session.add_user_message("active")
        store.persist(archived_session, "build")
        store.persist(active_session, "build")
        store.archive_session(archived_session.session_id)

        result = store.cleanup(max_sessions=1)

        self.assertEqual(result["deleted"], 0)
        self.assertTrue(os.path.isfile(store.resolve_summary_path(archived_session.session_id)))
        self.assertTrue(os.path.isfile(store.resolve_summary_path(active_session.session_id)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_session_store.py::TestSessionSummaryStore -v
```

Expected: FAIL because `SessionSummaryStore` has no `rename_session` or `archive_session`, `list_summaries` does not accept `include_archived`, and cleanup does not preserve archived sessions.

- [ ] **Step 3: Extend `ProjectionDb` schema and listing**

In `src/embedagent/projection_db.py`, update `initialize()` so `_ensure_columns()` receives the existing columns plus thread metadata:

```python
                self._ensure_columns(
                    connection,
                    "session_projection",
                    {
                        "started_at": "TEXT",
                        "user_goal": "TEXT",
                        "transcript_ref": "TEXT",
                        "summary_ref": "TEXT",
                        "title": "TEXT",
                        "archived": "INTEGER NOT NULL DEFAULT 0",
                        "archived_at": "TEXT",
                        "forked_from": "TEXT",
                        "forked_at": "TEXT",
                    },
                )
```

Update `upsert_session_projection()` INSERT/UPDATE SQL to include the new columns:

```python
                    INSERT INTO session_projection (
                      session_id, updated_at, current_mode, started_at, turn_count, message_count,
                      user_goal, transcript_ref, summary_ref,
                      last_transition_reason, last_transition_message, summary_text,
                      title, archived, archived_at, forked_from, forked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                      summary_text=excluded.summary_text,
                      title=excluded.title,
                      archived=excluded.archived,
                      archived_at=excluded.archived_at,
                      forked_from=excluded.forked_from,
                      forked_at=excluded.forked_at
```

Update the parameter tuple:

```python
                        payload.get("title"),
                        1 if payload.get("archived") else 0,
                        payload.get("archived_at"),
                        payload.get("forked_from"),
                        payload.get("forked_at"),
```

Replace `list_session_projections()` with:

```python
    def list_session_projections(
        self,
        limit: int = 10,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        self.initialize()
        with self._lock:
            connection = self._connect()
            try:
                if include_archived:
                    rows = connection.execute(
                        "SELECT * FROM session_projection ORDER BY updated_at DESC LIMIT ?",
                        (int(limit),),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM session_projection "
                        "WHERE COALESCE(archived, 0) = 0 "
                        "ORDER BY updated_at DESC LIMIT ?",
                        (int(limit),),
                    ).fetchall()
                return [dict(row) for row in rows]
            finally:
                connection.close()
```

- [ ] **Step 4: Add thread metadata helpers to `SessionSummaryStore`**

In `src/embedagent/session_store.py`, add `uuid` to imports near the top:

```python
import uuid
```

Add constants near helper functions:

```python
THREAD_TITLE_LIMIT = 120
```

In `SessionSummaryStore.persist()`, after `payload = self._build_payload(...)`, preserve previous thread metadata:

```python
            if previous is not None and isinstance(previous.get("thread"), dict):
                payload["thread"] = self._normalize_thread_metadata(previous.get("thread"))
```

In the `upsert_session_projection()` call inside `persist()`, add:

```python
                title=payload.get("title"),
                archived=bool(payload.get("thread", {}).get("archived")),
                archived_at=payload.get("thread", {}).get("archived_at"),
                forked_from=payload.get("thread", {}).get("forked_from"),
                forked_at=payload.get("thread", {}).get("forked_at"),
```

Change `list_summaries()` signature and projection call:

```python
    def list_summaries(
        self,
        limit: int = 10,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            items = self.projection_db.list_session_projections(
                limit=limit,
                include_archived=include_archived,
            )
            if not items:
                items = self._scan_summaries(include_archived=include_archived)
            normalized = []
            for item in items[:limit]:
                if not isinstance(item, dict):
                    continue
                normalized.append(self._summary_projection(dict(item)))
            return normalized
```

Add these methods to `SessionSummaryStore` after `load_summary()`:

```python
    def rename_session(self, session_id: str, title: str) -> Dict[str, Any]:
        normalized_title = self._normalize_thread_title(title)
        with self._lock:
            summary = self.load_summary(session_id)
            thread = self._normalize_thread_metadata(summary.get("thread"))
            thread["title"] = normalized_title
            summary["thread"] = thread
            summary["updated_at"] = _utc_now()
            return self._write_summary_payload(summary)

    def archive_session(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            summary = self.load_summary(session_id)
            thread = self._normalize_thread_metadata(summary.get("thread"))
            thread["archived"] = True
            thread["archived_at"] = _utc_now()
            summary["thread"] = thread
            summary["updated_at"] = _utc_now()
            return self._write_summary_payload(summary)

    def _write_summary_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("session_not_found")
        directory = os.path.join(self.root, session_id)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        summary_path = os.path.join(directory, "summary.json")
        thread = self._normalize_thread_metadata(payload.get("thread"))
        payload["thread"] = thread
        payload["title"] = self._display_title(payload)
        payload["summary_ref"] = os.path.relpath(summary_path, self.workspace).replace(os.sep, "/")
        _atomic_write_json(summary_path, sanitize_jsonable(payload))
        self._upsert_projection_from_summary(payload)
        return self._summary_projection(payload)

    def _upsert_projection_from_summary(self, payload: Dict[str, Any]) -> None:
        thread = self._normalize_thread_metadata(payload.get("thread"))
        self.projection_db.upsert_session_projection(
            session_id=payload.get("session_id"),
            updated_at=payload.get("updated_at") or _utc_now(),
            current_mode=payload.get("current_mode") or "explore",
            started_at=payload.get("started_at"),
            turn_count=int(payload.get("turn_count") or 0),
            message_count=int(payload.get("message_count") or 0),
            user_goal=payload.get("user_goal"),
            transcript_ref=payload.get("transcript_ref"),
            summary_ref=payload.get("summary_ref"),
            last_transition_reason=payload.get("last_transition_reason"),
            last_transition_message=payload.get("last_transition_message"),
            summary_text=payload.get("summary_text"),
            title=self._display_title(payload),
            archived=bool(thread.get("archived")),
            archived_at=thread.get("archived_at"),
            forked_from=thread.get("forked_from"),
            forked_at=thread.get("forked_at"),
        )

    def _summary_projection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_thread = payload.get("thread") if isinstance(payload.get("thread"), dict) else {}
        if not raw_thread:
            raw_thread = {
                "title": payload.get("title"),
                "archived": bool(payload.get("archived")),
                "archived_at": payload.get("archived_at"),
                "forked_from": payload.get("forked_from"),
                "forked_at": payload.get("forked_at"),
            }
        thread = self._normalize_thread_metadata(raw_thread)
        projection = dict(payload)
        projection["thread"] = thread
        projection["title"] = self._display_title(projection)
        projection["archived"] = bool(thread.get("archived"))
        projection["archived_at"] = str(thread.get("archived_at") or "")
        projection["forked_from"] = str(thread.get("forked_from") or "")
        projection["forked_at"] = str(thread.get("forked_at") or "")
        return projection

    def _display_title(self, payload: Dict[str, Any]) -> str:
        thread = self._normalize_thread_metadata(payload.get("thread"))
        return (
            str(thread.get("title") or "").strip()
            or str(payload.get("user_goal") or "").strip()
            or str(payload.get("summary_text") or "").strip()
            or ("Session %s" % str(payload.get("session_id") or "")[:8])
        )

    def _normalize_thread_title(self, title: str) -> str:
        normalized = str(title or "").strip()
        if not normalized:
            raise ValueError("invalid_thread_title")
        return _truncate_text(normalized, THREAD_TITLE_LIMIT)

    def _normalize_thread_metadata(self, value: Any) -> Dict[str, Any]:
        raw = value if isinstance(value, dict) else {}
        title = str(raw.get("title") or "").strip()
        if title:
            title = _truncate_text(title, THREAD_TITLE_LIMIT)
        return {
            "title": title,
            "archived": bool(raw.get("archived")),
            "archived_at": str(raw.get("archived_at") or ""),
            "forked_from": str(raw.get("forked_from") or ""),
            "forked_at": str(raw.get("forked_at") or ""),
        }
```

Update `_scan_summaries()` signature and body:

```python
    def _scan_summaries(self, include_archived: bool = False) -> List[Dict[str, Any]]:
```

Inside the loop, before appending:

```python
            thread = self._normalize_thread_metadata(payload.get("thread"))
            if thread.get("archived") and not include_archived:
                continue
```

Append records through `_summary_projection()`:

```python
            records.append(
                self._summary_projection(
                    {
                        "session_id": payload.get("session_id") or session_id,
                        "started_at": payload.get("started_at"),
                        "updated_at": payload.get("updated_at"),
                        "current_mode": payload.get("current_mode"),
                        "turn_count": payload.get("turn_count"),
                        "message_count": payload.get("message_count"),
                        "user_goal": payload.get("user_goal"),
                        "summary_text": payload.get("summary_text"),
                        "transcript_ref": payload.get("transcript_ref"),
                        "summary_ref": os.path.relpath(summary_path, self.workspace).replace(
                            os.sep, "/"
                        ),
                        "thread": thread,
                    }
                )
            )
```

Update `cleanup()` so archived sessions are retained even when hidden from the
normal thread list. Replace:

```python
            summaries = self.list_summaries(limit=self.max_index_entries)
```

with:

```python
            summaries = self.list_summaries(
                limit=self.max_index_entries,
                include_archived=True,
            )
```

- [ ] **Step 5: Run store tests**

Run:

```bash
uv run pytest tests/test_session_store.py::TestSessionSummaryStore -v
```

Expected: PASS.

- [ ] **Step 6: Commit store metadata**

```bash
git add src/embedagent/projection_db.py src/embedagent/session_store.py tests/test_session_store.py
git commit -m "core: add session thread metadata"
```

Expected: commit succeeds.

## Task 2: Fork Session Transcript Copy

**Files:**
- Modify: `src/embedagent/session_store.py`
- Test: `tests/test_session_store.py`

- [ ] **Step 1: Write failing fork test**

Add imports at the top of `tests/test_session_store.py`:

```python
from embedagent.transcript_store import TranscriptStore
```

Append this test to `TestSessionSummaryStore`:

```python
    def test_fork_session_copies_transcript_with_new_session_id_and_thread_metadata(self):
        store = SessionSummaryStore(self.workspace)
        transcript_store = TranscriptStore(self.workspace)
        session = Session()
        session.add_user_message("source goal")
        summary_ref = store.persist(session, "debug")
        transcript_store.append_event(
            session.session_id,
            "session_meta",
            {"current_mode": "debug", "session_id": session.session_id},
        )
        transcript_store.append_event(
            session.session_id,
            "user",
            {
                "role": "user",
                "content": "source goal",
                "message_id": "m-source",
                "session_id": session.session_id,
            },
        )
        store.rename_session(session.session_id, "Source Title")

        forked = store.fork_session(session.session_id, title="Fork Title")

        self.assertNotEqual(forked["session_id"], session.session_id)
        self.assertEqual(forked["thread"]["title"], "Fork Title")
        self.assertEqual(forked["thread"]["forked_from"], session.session_id)
        self.assertTrue(forked["thread"]["forked_at"])
        source_summary = store.load_summary(summary_ref)
        self.assertEqual(source_summary["thread"]["title"], "Source Title")
        fork_events = transcript_store.load_events(forked["session_id"])
        self.assertEqual(fork_events[0]["session_id"], forked["session_id"])
        self.assertEqual(fork_events[0]["payload"]["session_id"], forked["session_id"])
        self.assertEqual(fork_events[1]["session_id"], forked["session_id"])
        self.assertEqual(fork_events[1]["payload"]["session_id"], forked["session_id"])
        listed = store.list_summaries(limit=5)
        self.assertEqual(listed[0]["session_id"], forked["session_id"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_session_store.py::TestSessionSummaryStore::test_fork_session_copies_transcript_with_new_session_id_and_thread_metadata -v
```

Expected: FAIL because `fork_session` is missing.

- [ ] **Step 3: Implement transcript copy and summary clone**

In `src/embedagent/session_store.py`, add this method to `SessionSummaryStore` near `archive_session()`:

```python
    def fork_session(self, session_id: str, title: str = "") -> Dict[str, Any]:
        with self._lock:
            source = self.load_summary(session_id)
            source_id = str(source.get("session_id") or session_id).strip()
            if not source_id:
                raise ValueError("session_not_found")
            new_session_id = uuid.uuid4().hex
            now = _utc_now()
            source_transcript = self.transcript_store.resolve_transcript_path(source_id)
            target_transcript = self.transcript_store.resolve_transcript_path(new_session_id)
            if not os.path.isfile(source_transcript):
                raise ValueError("session_fork_failed")
            target_dir = os.path.dirname(target_transcript)
            if not os.path.isdir(target_dir):
                os.makedirs(target_dir)
            self._copy_transcript_for_fork(source_transcript, target_transcript, source_id, new_session_id)
            fork_thread = self._normalize_thread_metadata(source.get("thread"))
            fork_title = str(title or "").strip()
            if fork_title:
                fork_thread["title"] = self._normalize_thread_title(fork_title)
            elif fork_thread.get("title"):
                fork_thread["title"] = self._normalize_thread_title(
                    "%s Copy" % fork_thread.get("title")
                )
            fork_thread["archived"] = False
            fork_thread["archived_at"] = ""
            fork_thread["forked_from"] = source_id
            fork_thread["forked_at"] = now
            payload = dict(source)
            payload["session_id"] = new_session_id
            payload["updated_at"] = now
            payload["transcript_ref"] = self.transcript_ref_for_session(new_session_id)
            payload["thread"] = fork_thread
            payload["title"] = self._display_title(payload)
            return self._write_summary_payload(payload)

    def _copy_transcript_for_fork(
        self,
        source_path: str,
        target_path: str,
        source_session_id: str,
        target_session_id: str,
    ) -> None:
        with open(source_path, "r", encoding="utf-8") as source_handle:
            lines = source_handle.readlines()
        with open(target_path, "w", encoding="utf-8", newline="\n") as target_handle:
            for line in lines:
                text = line.strip()
                if not text:
                    continue
                try:
                    event = json.loads(text)
                except (TypeError, ValueError):
                    raise ValueError("session_fork_failed")
                if not isinstance(event, dict):
                    raise ValueError("session_fork_failed")
                if str(event.get("session_id") or "") == source_session_id:
                    event["session_id"] = target_session_id
                payload = event.get("payload")
                if isinstance(payload, dict) and str(payload.get("session_id") or "") == source_session_id:
                    payload["session_id"] = target_session_id
                target_handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run fork test**

Run:

```bash
uv run pytest tests/test_session_store.py::TestSessionSummaryStore::test_fork_session_copies_transcript_with_new_session_id_and_thread_metadata -v
```

Expected: PASS.

- [ ] **Step 5: Run all store tests**

Run:

```bash
uv run pytest tests/test_session_store.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit fork support**

```bash
git add src/embedagent/session_store.py tests/test_session_store.py
git commit -m "core: support session thread fork"
```

Expected: commit succeeds.

## Task 3: Core Lifecycle Facade

**Files:**
- Modify: `src/embedagent/services/session_lifecycle.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_services.py`
- Test: `tests/test_characterization.py`

- [ ] **Step 1: Write failing lifecycle manager tests**

Append these tests inside `TestSessionLifecycleManager` in `tests/test_services.py`:

```python
    def test_thread_lifecycle_delegates_to_summary_store(self):
        self.summary_store.rename_session.return_value = {"session_id": "sess-1", "title": "Renamed"}
        self.summary_store.archive_session.return_value = {
            "session_id": "sess-1",
            "thread": {"archived": True},
        }
        self.summary_store.fork_session.return_value = {"session_id": "sess-2"}

        renamed = self.manager.rename_session("sess-1", "Renamed")
        archived = self.manager.archive_session("sess-1")
        forked = self.manager.fork_session("sess-1", "Copy")

        self.summary_store.rename_session.assert_called_once_with("sess-1", "Renamed")
        self.summary_store.archive_session.assert_called_once_with("sess-1")
        self.summary_store.fork_session.assert_called_once_with("sess-1", title="Copy")
        self.assertEqual(renamed["title"], "Renamed")
        self.assertTrue(archived["thread"]["archived"])
        self.assertEqual(forked["session_id"], "sess-2")

    def test_list_sessions_passes_include_archived(self):
        self.summary_store.list_summaries.return_value = [{"id": "archived"}]

        result = self.manager.list_sessions(limit=20, include_archived=True)

        self.summary_store.list_summaries.assert_called_once_with(
            limit=20,
            include_archived=True,
        )
        self.assertEqual(result, [{"id": "archived"}])
```

Add this test to `TestServiceDelegation` in `tests/test_characterization.py`:

```python
    def test_inprocess_adapter_exposes_thread_lifecycle_facade(self, fresh_container):
        adapter = self._make_adapter(fresh_container)

        assert callable(adapter.rename_session)
        assert callable(adapter.archive_session)
        assert callable(adapter.fork_session)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_services.py::TestSessionLifecycleManager tests/test_characterization.py::TestServiceDelegation::test_inprocess_adapter_exposes_thread_lifecycle_facade -v
```

Expected: FAIL because methods/signature do not exist.

- [ ] **Step 3: Add lifecycle manager methods**

In `src/embedagent/services/session_lifecycle.py`, replace `list_sessions()` with:

```python
    def list_sessions(
        self,
        limit: int = 10,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        return self.summary_store.list_summaries(
            limit=limit,
            include_archived=include_archived,
        )
```

Add methods below it:

```python
    def rename_session(self, session_id: str, title: str) -> Dict[str, Any]:
        return self.summary_store.rename_session(session_id, title)

    def archive_session(self, session_id: str) -> Dict[str, Any]:
        return self.summary_store.archive_session(session_id)

    def fork_session(self, session_id: str, title: str = "") -> Dict[str, Any]:
        return self.summary_store.fork_session(session_id, title=title)
```

- [ ] **Step 4: Add `InProcessAdapter` facade methods**

In `src/embedagent/inprocess_adapter.py`, replace `list_sessions()` with:

```python
    def list_sessions(
        self,
        limit: int = 10,
        include_archived: bool = False,
    ) -> List[Dict[str, Any]]:
        return self._session_lifecycle.list_sessions(
            limit=limit,
            include_archived=include_archived,
        )
```

Add methods below it:

```python
    def rename_session(self, session_id: str, title: str) -> Dict[str, Any]:
        return self._session_lifecycle.rename_session(session_id, title)

    def archive_session(self, session_id: str) -> Dict[str, Any]:
        return self._session_lifecycle.archive_session(session_id)

    def fork_session(self, session_id: str, title: str = "") -> Dict[str, Any]:
        return self._session_lifecycle.fork_session(session_id, title=title)
```

- [ ] **Step 5: Run lifecycle facade tests**

Run:

```bash
uv run pytest tests/test_services.py::TestSessionLifecycleManager tests/test_characterization.py::TestServiceDelegation::test_inprocess_adapter_exposes_thread_lifecycle_facade -v
```

Expected: PASS.

- [ ] **Step 6: Commit lifecycle facade**

```bash
git add src/embedagent/services/session_lifecycle.py src/embedagent/inprocess_adapter.py tests/test_services.py tests/test_characterization.py
git commit -m "core: expose session thread lifecycle facade"
```

Expected: commit succeeds.

## Task 4: GUI Backend Routes And App Capabilities

**Files:**
- Modify: `src/embedagent/frontend/gui/backend/app_shell.py`
- Modify: `src/embedagent/frontend/gui/backend/server.py`
- Test: `tests/test_gui_app_shell.py`
- Test: `tests/test_gui_backend_api.py`

- [ ] **Step 1: Write failing app-shell capability test**

In `tests/test_gui_app_shell.py`, update existing capability assertions in `test_bootstrap_without_workspace_includes_shell_fields` to include:

```python
        self.assertEqual(
            payload["capabilities"]["thread_lifecycle"],
            {"rename": True, "fork": True, "archive": True},
        )
```

- [ ] **Step 2: Write failing GUI route tests**

Add this fake core to `tests/test_gui_backend_api.py` near `_ResourceReloadCore`:

```python
class _ThreadLifecycleCore(_FakeCore):
    def __init__(self):
        super().__init__()
        self.calls = []

    def rename_session(self, session_id, title):
        self.calls.append(("rename", session_id, title))
        return {
            "session_id": session_id,
            "title": title,
            "thread": {
                "title": title,
                "archived": False,
                "archived_at": "",
                "forked_from": "",
                "forked_at": "",
            },
        }

    def archive_session(self, session_id):
        self.calls.append(("archive", session_id))
        return {
            "session_id": session_id,
            "thread": {
                "title": "",
                "archived": True,
                "archived_at": "2026-06-17T00:00:00Z",
                "forked_from": "",
                "forked_at": "",
            },
        }

    def fork_session(self, session_id, title=""):
        self.calls.append(("fork", session_id, title))
        return {
            "session_id": "sess-fork",
            "title": title or "Copy",
            "thread": {
                "title": title or "Copy",
                "archived": False,
                "archived_at": "",
                "forked_from": session_id,
                "forked_at": "2026-06-17T00:00:00Z",
            },
        }
```

Append these tests to `TestGuiBackendApi`:

```python
    def test_thread_lifecycle_routes_call_core(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            core = _ThreadLifecycleCore()
            backend = GUIBackend(core, static_dir=static_dir)

            routes = {}
            for item in backend.app.routes:
                path = getattr(item, "path", "")
                if path in (
                    "/api/sessions/{session_id}/rename",
                    "/api/sessions/{session_id}/archive",
                    "/api/sessions/{session_id}/fork",
                ):
                    routes[path] = item

            rename_payload = asyncio.run(
                routes["/api/sessions/{session_id}/rename"].endpoint(
                    "sess-1",
                    {"title": "Renamed"},
                )
            )
            archive_payload = asyncio.run(
                routes["/api/sessions/{session_id}/archive"].endpoint("sess-1")
            )
            fork_payload = asyncio.run(
                routes["/api/sessions/{session_id}/fork"].endpoint(
                    "sess-1",
                    {"title": "Copy"},
                )
            )

        self.assertEqual(
            core.calls,
            [
                ("rename", "sess-1", "Renamed"),
                ("archive", "sess-1"),
                ("fork", "sess-1", "Copy"),
            ],
        )
        self.assertEqual(rename_payload["session"]["title"], "Renamed")
        self.assertTrue(archive_payload["session"]["thread"]["archived"])
        self.assertEqual(fork_payload["session_id"], "sess-fork")
        self.assertEqual(fork_payload["session"]["thread"]["forked_from"], "sess-1")

    def test_thread_lifecycle_errors_map_to_http_status(self):
        with tempfile.TemporaryDirectory() as static_dir:
            with open(os.path.join(static_dir, "index.html"), "w", encoding="utf-8") as handle:
                handle.write("<html><body>ok</body></html>")
            backend = GUIBackend(_ErrorCore("invalid_thread_title"), static_dir=static_dir)
            route = None
            for item in backend.app.routes:
                if getattr(item, "path", "") == "/api/sessions/{session_id}/rename":
                    route = item
                    break
            self.assertIsNotNone(route)
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(route.endpoint("sess-1", {"title": ""}))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail, "invalid_thread_title")
```

- [ ] **Step 3: Run GUI backend tests to verify they fail**

Run:

```bash
uv run pytest tests/test_gui_app_shell.py tests/test_gui_backend_api.py -v
```

Expected: FAIL because capability and routes are missing.

- [ ] **Step 4: Add app capability metadata**

In `src/embedagent/frontend/gui/backend/app_shell.py`, update `_capabilities()`:

```python
            "thread_lifecycle": {
                "rename": True,
                "fork": True,
                "archive": True,
            },
```

- [ ] **Step 5: Add safe session projection serializer and routes**

In `src/embedagent/frontend/gui/backend/server.py`, add a helper near other serializers:

```python
def _serialize_session_summary(payload: Any) -> Dict[str, Any]:
    data = dict(payload or {})
    thread = data.get("thread") if isinstance(data.get("thread"), dict) else {}
    safe_thread = {
        "title": str(thread.get("title") or ""),
        "archived": bool(thread.get("archived")),
        "archived_at": str(thread.get("archived_at") or ""),
        "forked_from": str(thread.get("forked_from") or ""),
        "forked_at": str(thread.get("forked_at") or ""),
    }
    return {
        "session_id": str(data.get("session_id") or ""),
        "title": str(data.get("title") or safe_thread.get("title") or ""),
        "current_mode": str(data.get("current_mode") or ""),
        "updated_at": str(data.get("updated_at") or ""),
        "summary_ref": str(data.get("summary_ref") or ""),
        "transcript_ref": str(data.get("transcript_ref") or ""),
        "thread": safe_thread,
    }


def _thread_lifecycle_http_error(exc: ValueError) -> HTTPException:
    detail = str(exc or "").strip() or "thread_lifecycle_failed"
    if "session_id 不存在" in detail or detail == "session_not_found":
        return HTTPException(status_code=404, detail="session_not_found")
    if detail == "invalid_thread_title":
        return HTTPException(status_code=422, detail=detail)
    if detail == "session_fork_failed":
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=detail)
```

Add routes after `resume_session()`:

```python
        @app.post("/api/sessions/{session_id}/rename")
        async def rename_session(session_id: str, request: Dict[str, Any]):
            core = self._require_core()
            try:
                summary = core.rename_session(
                    session_id,
                    str(request.get("title") or ""),
                )
            except ValueError as exc:
                raise _thread_lifecycle_http_error(exc)
            return {"session": _serialize_session_summary(summary)}

        @app.post("/api/sessions/{session_id}/archive")
        async def archive_session(session_id: str):
            core = self._require_core()
            try:
                summary = core.archive_session(session_id)
            except ValueError as exc:
                raise _thread_lifecycle_http_error(exc)
            return {"session": _serialize_session_summary(summary)}

        @app.post("/api/sessions/{session_id}/fork")
        async def fork_session(session_id: str, request: Dict[str, Any]):
            core = self._require_core()
            try:
                summary = core.fork_session(
                    session_id,
                    str(request.get("title") or ""),
                )
            except ValueError as exc:
                raise _thread_lifecycle_http_error(exc)
            payload = _serialize_session_summary(summary)
            return {"session_id": payload["session_id"], "session": payload}
```

- [ ] **Step 6: Run GUI backend tests**

Run:

```bash
uv run pytest tests/test_gui_app_shell.py tests/test_gui_backend_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit GUI backend lifecycle**

```bash
git add src/embedagent/frontend/gui/backend/app_shell.py src/embedagent/frontend/gui/backend/server.py tests/test_gui_app_shell.py tests/test_gui_backend_api.py
git commit -m "gui: expose thread lifecycle api"
```

Expected: commit succeeds.

## Task 5: Frontend Thread Lifecycle Wiring

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/app-home-model.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`

- [ ] **Step 1: Write failing frontend model tests**

In `src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs`, add after app capability assertions:

```javascript
  assert.equal(initial.capabilities.threadLifecycle.rename, false);
  assert.equal(initial.capabilities.threadLifecycle.fork, false);
  assert.equal(initial.capabilities.threadLifecycle.archive, false);
```

Update the `bootstrap` capabilities payload to include:

```javascript
      thread_lifecycle: { rename: true, fork: true, archive: true },
```

Add assertions after bootstrap capability assertions:

```javascript
  assert.equal(bootstrap.capabilities.threadLifecycle.rename, true);
  assert.equal(bootstrap.capabilities.threadLifecycle.fork, true);
  assert.equal(bootstrap.capabilities.threadLifecycle.archive, true);
```

In `src/embedagent/frontend/gui/webapp/test/app-home-model.test.mjs`, add `threadLifecycleCapabilities` to the first `buildAppHomeModel()` call:

```javascript
    threadLifecycleCapabilities: { rename: true, fork: true, archive: true },
```

Change expected first action enabled assertion:

```javascript
  assert.equal(model.threads.rows[0].actions[0].enabled, true);
  assert.equal(model.threads.rows[0].actions[0].reason, "");
```

Add a session in the first sessions array:

```javascript
      {
        session_id: "sess-renamed",
        title: "Manual title",
        thread: { title: "Thread metadata title" },
        user_goal: "Should not win",
        current_mode: "verify",
        updated_at: "",
      },
```

Add assertions:

```javascript
  assert.equal(model.threads.rows[2].title, "Thread metadata title");
  assert.equal(model.threads.rows[2].mode, "verify");
```

- [ ] **Step 2: Write failing source-contract assertions**

In `src/embedagent/frontend/gui/webapp/test/run-tests.mjs`, add these assertions near existing `appSource` assertions:

```javascript
  assert.equal(appSource.includes("renameThread"), true);
  assert.equal(appSource.includes("archiveThread"), true);
  assert.equal(appSource.includes("forkThread"), true);
  assert.equal(appSource.includes('/rename"'), true);
  assert.equal(appSource.includes('/archive"'), true);
  assert.equal(appSource.includes('/fork"'), true);
```

Add near `appHomeModelSource` assertions:

```javascript
  assert.equal(appHomeModelSource.includes("session.thread?.title"), true);
```

- [ ] **Step 3: Run frontend tests to verify they fail**

Run:

```bash
npm test
```

Expected: FAIL because `threadLifecycle` normalization and real action handlers do not exist.

- [ ] **Step 4: Normalize thread lifecycle capabilities**

In `src/embedagent/frontend/gui/webapp/src/app-shell/model.js`, add helper:

```javascript
function normalizeThreadLifecycle(input = {}) {
  const raw = snakeOrCamel(input, "thread_lifecycle", "threadLifecycle", {});
  const value = raw && typeof raw === "object" ? raw : {};
  return {
    rename: value.rename === true,
    fork: value.fork === true,
    archive: value.archive === true,
  };
}
```

Update `normalizeAppCapabilities()` return object:

```javascript
    threadLifecycle: normalizeThreadLifecycle(input),
```

- [ ] **Step 5: Prefer thread title in app-home model**

In `src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js`, replace title selection inside `threadRows.map()` with:

```javascript
        title:
          String(session.thread?.title || "").trim()
          || String(session.title || "").trim()
          || String(session.user_goal || "").trim()
          || String(session.summary_text || "").trim()
          || `Session ${sessionId.slice(0, 8)}`,
```

In `App.jsx`, update `buildAppHomeModel()` call near the bottom to pass:

```javascript
      threadLifecycleCapabilities: state.app.capabilities?.threadLifecycle || {},
```

- [ ] **Step 6: Add lifecycle API handlers**

In `src/embedagent/frontend/gui/webapp/src/App.jsx`, replace `handleThreadLifecycleAction()` with:

```javascript
  async function renameThread(sessionId) {
    const current = (state.sessions || []).find((item) => item.session_id === sessionId) || {};
    const initialTitle = current.thread?.title || current.title || current.user_goal || "";
    const title = window.prompt("Rename thread", initialTitle);
    if (title === null) return;
    const normalizedTitle = String(title || "").trim();
    if (!normalizedTitle) {
      dispatch({
        type: "interaction_notice_set",
        notice: {
          kind: "thread_lifecycle",
          title: "Rename failed",
          body: "Thread title cannot be empty.",
        },
      });
      return;
    }
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: normalizedTitle }),
    });
    await loadSessions();
  }

  async function archiveThread(sessionId) {
    const ok = window.confirm("Archive this thread?");
    if (!ok) return;
    await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/archive`, {
      method: "POST",
    });
    await loadSessions();
    dispatch({
      type: "interaction_notice_set",
      notice: {
        kind: "thread_lifecycle",
        title: "Thread archived",
        body: "The thread was archived and hidden from the normal thread list.",
      },
    });
  }

  async function forkThread(sessionId) {
    const title = window.prompt("Fork thread title", "");
    if (title === null) return;
    const payload = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}/fork`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: String(title || "").trim() }),
    });
    await loadSessions();
    if (payload.session_id) {
      await loadSession(payload.session_id);
    }
  }

  async function handleThreadLifecycleAction(actionId, sessionId) {
    try {
      if (actionId === "rename") {
        await renameThread(sessionId);
        return;
      }
      if (actionId === "archive") {
        await archiveThread(sessionId);
        return;
      }
      if (actionId === "fork") {
        await forkThread(sessionId);
        return;
      }
    } catch (error) {
      dispatch({
        type: "interaction_notice_set",
        notice: {
          kind: "thread_lifecycle",
          title: "Thread action failed",
          body: error?.message || String(error || "thread_lifecycle_failed"),
        },
      });
    }
  }
```

- [ ] **Step 7: Run frontend tests**

Run:

```bash
npm test
```

Expected: PASS.

- [ ] **Step 8: Commit frontend wiring**

```bash
git add src/embedagent/frontend/gui/webapp/src/app-shell/model.js src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/test/app-shell-model.test.mjs src/embedagent/frontend/gui/webapp/test/app-home-model.test.mjs src/embedagent/frontend/gui/webapp/test/run-tests.mjs
git commit -m "gui: wire thread lifecycle actions"
```

Expected: commit succeeds.

## Task 6: Static Assets, Documentation, Archive, And Verification

**Files:**
- Modify: `src/embedagent/frontend/gui/static/assets/app.css` if build changes it
- Modify: `src/embedagent/frontend/gui/static/assets/app.js`
- Modify: `src/embedagent/frontend/gui/static/index.html` if build changes it
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/modules/frontend-gui.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/README.md`
- Modify: `docs/archive/README.md`
- Create: `docs/archive/gui-thread-lifecycle-boundary/README.md`
- Move: `docs/superpowers/specs/2026-06-17-gui-thread-lifecycle-boundary-design.md`
- Move: `docs/superpowers/plans/2026-06-17-gui-thread-lifecycle-boundary.md`

- [ ] **Step 1: Build frontend static assets**

Run:

```bash
npm run build
```

Expected: PASS. Static assets under `src/embedagent/frontend/gui/static/` are updated only if bundle content changes.

- [ ] **Step 2: Update source-of-truth docs**

Update active docs with this durable wording in the listed sections:

```markdown
GUI thread lifecycle operations (`rename`, `fork`, and `archive`) are exposed through the session lifecycle facade and consumed by the GUI app shell. They update session summary/projection metadata used by app thread lists; they do not rewrite transcript history, own workflow state, activate tools, decide permissions, load extensions, or create source-control checkpoints.
```

- In `README.md`, add a bullet beside the official GUI app-shell boundary bullet.
- In `AGENTS.md`, add the same boundary rule under `Frontend / Protocol Policy`.
- In `docs/overall-solution-architecture.md`, add it to the frontend/GUI boundary section.
- In `docs/frontend-protocol.md`, add it near the app-shell bootstrap/session summary contract.
- In `docs/modules/frontend-gui.md`, replace the current note that thread lifecycle actions are disabled with the new backend-backed lifecycle boundary.
- In `docs/implementation-roadmap.md`, update the recent GUI app-shell work paragraph and remove thread lifecycle from the immediate remaining GUI gap list.
- In `docs/development-tracker.md`, add a dated entry for this slice and update the latest GUI closeout paragraph.
- In `docs/design-change-log.md`, add a dated change entry with the ownership boundary and no-ADR decision.

- [ ] **Step 3: Archive slice-local spec and plan**

Create archive directory:

```bash
New-Item -ItemType Directory -Force docs\archive\gui-thread-lifecycle-boundary
```

Move files with Git:

```bash
git mv docs\superpowers\specs\2026-06-17-gui-thread-lifecycle-boundary-design.md docs\archive\gui-thread-lifecycle-boundary\
git mv docs\superpowers\plans\2026-06-17-gui-thread-lifecycle-boundary.md docs\archive\gui-thread-lifecycle-boundary\
```

Create `docs/archive/gui-thread-lifecycle-boundary/README.md`:

```markdown
# GUI Thread Lifecycle Boundary Archive

> Status: `archive`

This archive package contains the completed design and implementation plan for
the GUI thread lifecycle boundary slice.

Durable conclusions have been synchronized into active source-of-truth docs:

- `README.md`
- `AGENTS.md`
- `docs/overall-solution-architecture.md`
- `docs/frontend-protocol.md`
- `docs/modules/frontend-gui.md`
- `docs/implementation-roadmap.md`
- `docs/development-tracker.md`
- `docs/design-change-log.md`

Archived slice materials:

- `2026-06-17-gui-thread-lifecycle-boundary-design.md`
- `2026-06-17-gui-thread-lifecycle-boundary.md`

Current architecture truth lives in active docs, not in this archive package.
```

Update `docs/archive/README.md` and `docs/README.md` to include this archive package.

- [ ] **Step 4: Run targeted backend tests**

Run:

```bash
uv run pytest tests/test_session_store.py tests/test_services.py tests/test_characterization.py::TestServiceDelegation tests/test_gui_backend_api.py tests/test_gui_app_shell.py tests/test_gui_app_host.py -v
```

Expected: PASS.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
npm test
```

Expected: PASS.

- [ ] **Step 6: Run lint**

Run:

```bash
uv run ruff check src/embedagent/frontend/gui/backend src/embedagent/projection_db.py src/embedagent/session_store.py src/embedagent/services/session_lifecycle.py src/embedagent/inprocess_adapter.py tests/test_session_store.py tests/test_services.py tests/test_characterization.py tests/test_gui_backend_api.py tests/test_gui_app_shell.py tests/test_gui_app_host.py
```

Expected: PASS.

- [ ] **Step 7: Run fast suite with local temp workaround**

Run:

```bash
$env:TEMP='D:\Project\coding_agent\.worktrees\gui-thread-lifecycle-boundary\.venv\pytest-tmp'; $env:TMP='D:\Project\coding_agent\.worktrees\gui-thread-lifecycle-boundary\.venv\pytest-tmp'; New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null; uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS. This uses a workspace-local temp directory to avoid the known Windows global pytest temp permission issue.

- [ ] **Step 8: Verify no Core ownership regression**

Run:

```bash
git diff -- src/embedagent/query_engine.py src/embedagent/agent_loop.py src/embedagent/agent_tool_action_service.py src/embedagent/extensions.py src/embedagent/permissions.py
```

Expected: no output.

- [ ] **Step 9: Commit docs, archive, and static assets**

```bash
git add README.md AGENTS.md docs src/embedagent/frontend/gui/static src/embedagent/frontend/gui/webapp
git commit -m "docs: document gui thread lifecycle boundary"
```

Expected: commit succeeds.

## Final Self-Review Checklist

- [ ] Spec coverage: store/projection metadata, fork transcript copy, facade, GUI routes, app capabilities, frontend wiring, docs, and archive are each covered by a task.
- [ ] Placeholder scan: no unresolved markers or vague "add tests" language remains.
- [ ] Type consistency: `thread_lifecycle` backend JSON maps to frontend `threadLifecycle`; store methods and facade methods consistently use `rename_session`, `archive_session`, and `fork_session`.
- [ ] Python compatibility: no walrus operator, pattern matching, `dict | dict`, or Python 3.9+ typing syntax.
- [ ] Runtime compatibility: no new dependencies, no network requirement, no Docker/WSL/VS Code dependency.
