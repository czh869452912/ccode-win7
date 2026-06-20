# Compacted History Checkpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable compacted-history checkpoints so future provider context can be rebuilt from a replacement history plus the newer transcript suffix.

**Architecture:** Keep `transcript.jsonl` as the append-only audit log. Add compacted-history state as a context/session-history checkpoint, not as a tool contract, permission shortcut, frontend policy, or workflow-package responsibility. Roll out in three behavior levels: reducer projection only, live event emission without active context changes, then context assembly from the latest valid checkpoint.

**Tech Stack:** Python 3.8, dataclasses, existing `Session`, `TranscriptStore`, `SessionRestorer`, `ContextManager`, `QueryEngine`, pytest.

---

## File Structure

- Create `src/embedagent/compacted_history.py`
  - Owns compacted-history records, reducer projection, validation helpers, and safe serialization.
- Modify `src/embedagent/session.py`
  - Adds live `CompactedHistoryCheckpoint` state and session helper methods.
- Modify `src/embedagent/session_restore.py`
  - Replays `compacted_history` events after validating anchors and replacement messages.
- Modify `src/embedagent/compaction_state.py`
  - Projects compacted-history diagnostics alongside legacy compact-boundary diagnostics.
- Modify `src/embedagent/query_engine.py`
  - Emits `compacted_history` after existing `compact_boundary` emission, without changing active context selection in the first slice.
- Modify `src/embedagent/context.py`
  - Later slices add a replacement-history base path for context assembly.
- Create `src/embedagent/compactor.py`
  - Later slices extract deterministic replacement-history construction behind a small compactor interface.
- Test `tests/test_compacted_history.py`
  - Covers reducer validation and serialization.
- Modify `tests/test_compaction_state.py`
  - Ensures compacted-history projection does not break legacy boundaries.
- Modify `tests/test_session_restore.py`
  - Ensures restore accepts valid checkpoints and rejects bad or duplicate checkpoints.
- Modify `tests/test_query_engine_refactor.py`
  - Ensures live compact retry emits both legacy and new events.
- Modify `tests/test_context_config.py`
  - Ensures context assembly uses replacement history only after the final slice.
- Modify durable docs after behavior changes:
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
  - `docs/design-change-log.md`

## Event Contract

Add schema v2 transcript events with `type == "compacted_history"` and this payload shape:

```json
{
  "checkpoint_id": "ch-...",
  "boundary_id": "cb-...",
  "summary_text": "Earlier work summary",
  "first_kept_message_id": "m-...",
  "replacement_messages": [
    {
      "role": "system",
      "content": "Earlier work summary",
      "kind": "compacted_history_summary",
      "metadata": {
        "checkpoint_id": "ch-...",
        "boundary_id": "cb-..."
      }
    }
  ],
  "trigger": "auto_threshold|reactive_retry|manual|resume_repair",
  "phase": "pre_provider|provider_retry|standalone",
  "token_counts": {"approx_before": 1000, "approx_after": 250},
  "message_counts": {"before": 10, "after": 4, "summarized_turns": 3, "recent_turns": 1},
  "file_activity": {"read_files": ["src/demo.c"], "modified_files": []},
  "evidence_refs": [".embedagent/memory/sessions/sess/tool-results/read-1/content.txt"],
  "extension_summary": false,
  "created_at": "2026-06-20T00:00:00Z",
  "metadata": {"pipeline_steps": ["reactive_compact_retry", "summary/compact"]}
}
```

Rules:

- `checkpoint_id` is required and unique within a restore prefix.
- `replacement_messages` must be a non-empty list of safe provider messages.
- Allowed replacement message roles are `system`, `user`, and `assistant`; tool messages are not allowed in checkpoint replacement history.
- `first_kept_message_id` is optional for legacy compatibility in Slice 1, but required before context assembly consumes the checkpoint.
- `summary_text` and replacement message content must be bounded by constants in `compacted_history.py`.
- Reducers may project checkpoints for diagnostics, but they must not select active context.

## Task 1: Add Compacted-History Reducer Projection

**Files:**
- Create: `src/embedagent/compacted_history.py`
- Modify: `src/embedagent/compaction_state.py`
- Create: `tests/test_compacted_history.py`
- Modify: `tests/test_compaction_state.py`

- [x] **Step 1: Write reducer tests for a valid checkpoint**

Create `tests/test_compacted_history.py` with this initial content:

```python
import json
import unittest

from embedagent.compacted_history import CompactedHistoryReducer


class TestCompactedHistoryReducer(unittest.TestCase):
    def test_reducer_projects_latest_valid_checkpoint(self):
        events = [
            {
                "schema_version": 2,
                "session_id": "sess-compact",
                "event_id": "evt-1",
                "seq": 11,
                "ts": "2026-06-20T00:00:00Z",
                "type": "compacted_history",
                "payload": {
                    "checkpoint_id": "ch-1",
                    "boundary_id": "cb-1",
                    "summary_text": "Earlier work summary",
                    "first_kept_message_id": "m-kept",
                    "replacement_messages": [
                        {
                            "role": "system",
                            "content": "Earlier work summary",
                            "kind": "compacted_history_summary",
                            "metadata": {"checkpoint_id": "ch-1", "boundary_id": "cb-1"},
                        }
                    ],
                    "trigger": "reactive_retry",
                    "phase": "provider_retry",
                    "token_counts": {"approx_before": 1800, "approx_after": 500},
                    "message_counts": {
                        "before": 12,
                        "after": 4,
                        "summarized_turns": 4,
                        "recent_turns": 2,
                    },
                    "file_activity": {
                        "read_files": ["src/demo.c", "src/demo.c"],
                        "modified_files": [],
                    },
                    "evidence_refs": ["ref-a", "ref-a"],
                    "extension_summary": False,
                    "created_at": "2026-06-20T00:00:00Z",
                    "metadata": {"pipeline_steps": ["reactive_compact_retry"]},
                },
            }
        ]

        state = CompactedHistoryReducer().reduce(events)
        payload = state.to_dict()

        self.assertEqual(payload["checkpoint_count"], 1)
        self.assertEqual(payload["latest_checkpoint_id"], "ch-1")
        self.assertEqual(payload["status"], "ready")
        latest = payload["latest_checkpoint"]
        self.assertEqual(latest["checkpoint_id"], "ch-1")
        self.assertEqual(latest["boundary_id"], "cb-1")
        self.assertEqual(latest["first_kept_message_id"], "m-kept")
        self.assertEqual(latest["replacement_message_count"], 1)
        self.assertEqual(latest["replacement_messages"][0]["role"], "system")
        self.assertEqual(latest["file_activity"]["read_files"], ["src/demo.c"])
        self.assertEqual(latest["evidence_refs"], ["ref-a"])
        self.assertEqual(payload["diagnostics"], [])
        json.dumps(payload, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the new test and verify it fails because the module is missing**

Run:

```bash
uv run pytest tests/test_compacted_history.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'embedagent.compacted_history'
```

- [x] **Step 3: Implement the minimal reducer module**

Create `src/embedagent/compacted_history.py`:

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

MAX_SUMMARY_CHARS = 12000
MAX_REPLACEMENT_MESSAGES = 12
MAX_REPLACEMENT_CONTENT_CHARS = 12000
ALLOWED_REPLACEMENT_ROLES = set(["system", "user", "assistant"])


def _clean_text(value: Any, limit: int = 0) -> str:
    text = str(value or "").strip()
    if limit > 0 and len(text) > limit:
        return text[:limit]
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _copy_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


def _stable_texts(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    seen = set()
    result = []
    for item in value:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return sorted(result)


def _int_counts(value: Any, allowed_keys: List[str]) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in allowed_keys:
        if key in value:
            result[key] = _safe_int(value.get(key))
    return result


def _safe_replacement_messages(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    messages = []
    for item in value[:MAX_REPLACEMENT_MESSAGES]:
        if not isinstance(item, dict):
            continue
        role = _clean_text(item.get("role"))
        if role not in ALLOWED_REPLACEMENT_ROLES:
            continue
        content = _clean_text(item.get("content"), MAX_REPLACEMENT_CONTENT_CHARS)
        if not content:
            continue
        message = {
            "role": role,
            "content": content,
        }
        kind = _clean_text(item.get("kind"))
        if kind:
            message["kind"] = kind
        metadata = _copy_dict(item.get("metadata"))
        if metadata:
            message["metadata"] = metadata
        messages.append(message)
    return messages


@dataclass
class CompactedHistoryCheckpoint(object):
    checkpoint_id: str
    boundary_id: str = ""
    summary_text: str = ""
    first_kept_message_id: str = ""
    replacement_messages: List[Dict[str, Any]] = field(default_factory=list)
    trigger: str = ""
    phase: str = ""
    token_counts: Dict[str, int] = field(default_factory=dict)
    message_counts: Dict[str, int] = field(default_factory=dict)
    file_activity: Dict[str, List[str]] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    extension_summary: bool = False
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    seq: int = 0
    ts: str = ""

    @property
    def replacement_message_count(self) -> int:
        return len(self.replacement_messages)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "boundary_id": self.boundary_id,
            "summary_text": self.summary_text,
            "first_kept_message_id": self.first_kept_message_id,
            "replacement_messages": [dict(item) for item in self.replacement_messages],
            "replacement_message_count": self.replacement_message_count,
            "trigger": self.trigger,
            "phase": self.phase,
            "token_counts": dict(self.token_counts),
            "message_counts": dict(self.message_counts),
            "file_activity": {
                "read_files": list(self.file_activity.get("read_files") or []),
                "modified_files": list(self.file_activity.get("modified_files") or []),
            },
            "evidence_refs": list(self.evidence_refs),
            "extension_summary": bool(self.extension_summary),
            "created_at": self.created_at,
            "metadata": _copy_dict(self.metadata),
            "event_id": self.event_id,
            "seq": int(self.seq or 0),
            "ts": self.ts,
        }


@dataclass
class CompactedHistoryState(object):
    checkpoints: List[CompactedHistoryCheckpoint] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def latest_checkpoint(self) -> Optional[CompactedHistoryCheckpoint]:
        if not self.checkpoints:
            return None
        return self.checkpoints[-1]

    def to_dict(self) -> Dict[str, Any]:
        latest = self.latest_checkpoint
        return {
            "checkpoint_count": len(self.checkpoints),
            "latest_checkpoint_id": latest.checkpoint_id if latest is not None else "",
            "latest_checkpoint": latest.to_dict() if latest is not None else {},
            "checkpoints": [item.to_dict() for item in self.checkpoints],
            "diagnostics": [dict(item) for item in self.diagnostics],
            "status": "ready" if self.checkpoints else "empty",
        }


class CompactedHistoryReducer(object):
    def reduce(self, events: List[Dict[str, Any]]) -> CompactedHistoryState:
        state = CompactedHistoryState()
        seen_checkpoint_ids = set()
        for event in list(events or []):
            if not isinstance(event, dict):
                continue
            if _clean_text(event.get("type")) != "compacted_history":
                continue
            payload = _copy_dict(event.get("payload"))
            checkpoint_id = _clean_text(payload.get("checkpoint_id"))
            if not checkpoint_id:
                state.diagnostics.append(self._diagnostic(event, "missing_checkpoint_id"))
                continue
            if checkpoint_id in seen_checkpoint_ids:
                state.diagnostics.append(
                    self._diagnostic(
                        event,
                        "duplicate_checkpoint_id",
                        checkpoint_id=checkpoint_id,
                    )
                )
                continue
            replacement_messages = _safe_replacement_messages(
                payload.get("replacement_messages")
            )
            if not replacement_messages:
                state.diagnostics.append(
                    self._diagnostic(
                        event,
                        "missing_replacement_messages",
                        checkpoint_id=checkpoint_id,
                    )
                )
                continue
            seen_checkpoint_ids.add(checkpoint_id)
            state.checkpoints.append(
                self._record_from_payload(checkpoint_id, replacement_messages, payload, event)
            )
        return state

    def _record_from_payload(
        self,
        checkpoint_id: str,
        replacement_messages: List[Dict[str, Any]],
        payload: Dict[str, Any],
        event: Dict[str, Any],
    ) -> CompactedHistoryCheckpoint:
        file_activity = payload.get("file_activity")
        if not isinstance(file_activity, dict):
            file_activity = {}
        return CompactedHistoryCheckpoint(
            checkpoint_id=checkpoint_id,
            boundary_id=_clean_text(payload.get("boundary_id")),
            summary_text=_clean_text(payload.get("summary_text"), MAX_SUMMARY_CHARS),
            first_kept_message_id=_clean_text(payload.get("first_kept_message_id")),
            replacement_messages=replacement_messages,
            trigger=_clean_text(payload.get("trigger")),
            phase=_clean_text(payload.get("phase")),
            token_counts=_int_counts(
                payload.get("token_counts"),
                ["approx_before", "approx_after"],
            ),
            message_counts=_int_counts(
                payload.get("message_counts"),
                ["before", "after", "summarized_turns", "recent_turns"],
            ),
            file_activity={
                "read_files": _stable_texts(file_activity.get("read_files")),
                "modified_files": _stable_texts(file_activity.get("modified_files")),
            },
            evidence_refs=_stable_texts(payload.get("evidence_refs")),
            extension_summary=bool(payload.get("extension_summary")),
            created_at=_clean_text(payload.get("created_at")),
            metadata=_copy_dict(payload.get("metadata")),
            event_id=_clean_text(event.get("event_id")),
            seq=_safe_int(event.get("seq")),
            ts=_clean_text(event.get("ts")),
        )

    def _diagnostic(
        self,
        event: Dict[str, Any],
        reason: str,
        checkpoint_id: str = "",
    ) -> Dict[str, Any]:
        return {
            "reason": reason,
            "checkpoint_id": checkpoint_id,
            "event_id": _clean_text(event.get("event_id")),
            "seq": _safe_int(event.get("seq")),
            "ts": _clean_text(event.get("ts")),
        }
```

- [x] **Step 4: Run the reducer test and verify it passes**

Run:

```bash
uv run pytest tests/test_compacted_history.py -q
```

Expected:

```text
1 passed
```

- [x] **Step 5: Add reducer diagnostics tests**

Append these tests to `tests/test_compacted_history.py` inside `TestCompactedHistoryReducer`:

```python
    def test_reducer_rejects_duplicate_checkpoint_id(self):
        events = [
            {
                "type": "compacted_history",
                "event_id": "evt-1",
                "seq": 1,
                "payload": {
                    "checkpoint_id": "ch-dup",
                    "summary_text": "First",
                    "replacement_messages": [{"role": "system", "content": "First"}],
                },
            },
            {
                "type": "compacted_history",
                "event_id": "evt-2",
                "seq": 2,
                "payload": {
                    "checkpoint_id": "ch-dup",
                    "summary_text": "Second",
                    "replacement_messages": [{"role": "system", "content": "Second"}],
                },
            },
        ]

        payload = CompactedHistoryReducer().reduce(events).to_dict()

        self.assertEqual(payload["checkpoint_count"], 1)
        self.assertEqual(payload["latest_checkpoint"]["summary_text"], "First")
        self.assertEqual(payload["diagnostics"][0]["reason"], "duplicate_checkpoint_id")
        self.assertEqual(payload["diagnostics"][0]["checkpoint_id"], "ch-dup")

    def test_reducer_rejects_empty_replacement_history(self):
        events = [
            {
                "type": "compacted_history",
                "event_id": "evt-empty",
                "seq": 1,
                "payload": {
                    "checkpoint_id": "ch-empty",
                    "summary_text": "No replacement messages",
                    "replacement_messages": [],
                },
            }
        ]

        payload = CompactedHistoryReducer().reduce(events).to_dict()

        self.assertEqual(payload["checkpoint_count"], 0)
        self.assertEqual(payload["status"], "empty")
        self.assertEqual(payload["diagnostics"][0]["reason"], "missing_replacement_messages")
        self.assertEqual(payload["diagnostics"][0]["checkpoint_id"], "ch-empty")

    def test_reducer_filters_unsafe_replacement_roles(self):
        events = [
            {
                "type": "compacted_history",
                "event_id": "evt-tool",
                "seq": 1,
                "payload": {
                    "checkpoint_id": "ch-tool",
                    "summary_text": "Mixed roles",
                    "replacement_messages": [
                        {"role": "tool", "content": "raw tool output"},
                        {"role": "system", "content": "safe summary"},
                    ],
                },
            }
        ]

        latest = CompactedHistoryReducer().reduce(events).to_dict()["latest_checkpoint"]

        self.assertEqual(latest["replacement_message_count"], 1)
        self.assertEqual(latest["replacement_messages"][0]["role"], "system")
        self.assertEqual(latest["replacement_messages"][0]["content"], "safe summary")
```

- [x] **Step 6: Run reducer diagnostics tests**

Run:

```bash
uv run pytest tests/test_compacted_history.py -q
```

Expected:

```text
4 passed
```

- [x] **Step 7: Project compacted history through compaction state**

Add to `tests/test_compaction_state.py`:

```python
    def test_compaction_state_projects_compacted_history_without_replacing_boundaries(self):
        events = [
            {
                "type": "compact_boundary",
                "event_id": "evt-boundary",
                "seq": 1,
                "payload": {
                    "boundary_id": "cb-1",
                    "summary_text": "Boundary summary",
                    "compacted_turn_count": 2,
                },
            },
            {
                "type": "compacted_history",
                "event_id": "evt-history",
                "seq": 2,
                "payload": {
                    "checkpoint_id": "ch-1",
                    "boundary_id": "cb-1",
                    "summary_text": "Checkpoint summary",
                    "first_kept_message_id": "m-kept",
                    "replacement_messages": [
                        {"role": "system", "content": "Checkpoint summary"}
                    ],
                },
            },
        ]

        payload = CompactionStateReducer().reduce(events).to_dict()

        self.assertEqual(payload["boundary_count"], 1)
        self.assertEqual(payload["latest_boundary_id"], "cb-1")
        self.assertEqual(payload["compacted_history"]["checkpoint_count"], 1)
        self.assertEqual(
            payload["compacted_history"]["latest_checkpoint"]["checkpoint_id"],
            "ch-1",
        )
```

- [x] **Step 8: Run the compaction state test and verify it fails**

Run:

```bash
uv run pytest tests/test_compaction_state.py::TestCompactionStateReducer::test_compaction_state_projects_compacted_history_without_replacing_boundaries -q
```

Expected:

```text
KeyError: 'compacted_history'
```

- [x] **Step 9: Add compacted-history projection to `CompactionState`**

Modify `src/embedagent/compaction_state.py`:

```python
from embedagent.compacted_history import CompactedHistoryReducer, CompactedHistoryState
```

Update the dataclass:

```python
@dataclass
class CompactionState(object):
    boundaries: List[CompactionBoundaryRecord] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    compacted_history: CompactedHistoryState = field(default_factory=CompactedHistoryState)
```

Update `to_dict()`:

```python
            "compacted_history": self.compacted_history.to_dict(),
```

Update `reduce()` before returning:

```python
        state.compacted_history = CompactedHistoryReducer().reduce(events)
        return state
```

- [x] **Step 10: Run reducer suites**

Run:

```bash
uv run pytest tests/test_compacted_history.py tests/test_compaction_state.py -q
```

Expected:

```text
passed
```

## Task 2: Add Live Session State And Restore Validation

**Files:**
- Modify: `src/embedagent/session.py`
- Modify: `src/embedagent/session_restore.py`
- Modify: `tests/test_session_restore.py`

- [x] **Step 1: Write restore test for a valid compacted-history event**

Add to `tests/test_session_restore.py`:

```python
    def test_restore_replays_valid_compacted_history_checkpoint(self):
        events = self._build_valid_transcript()
        events.append(
            {
                "schema_version": 2,
                "session_id": "sess-test",
                "event_id": "evt-4",
                "seq": 4,
                "ts": "2026-06-20T00:00:00Z",
                "type": "compacted_history",
                "payload": {
                    "checkpoint_id": "ch-1",
                    "summary_text": "Earlier work summary",
                    "first_kept_message_id": "m-user-1",
                    "replacement_messages": [
                        {
                            "role": "system",
                            "content": "Earlier work summary",
                            "kind": "compacted_history_summary",
                        }
                    ],
                },
            }
        )

        result = SessionRestorer().restore(events)

        checkpoint = result.session.latest_compacted_history()
        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint.checkpoint_id, "ch-1")
        self.assertEqual(checkpoint.first_kept_message_id, "m-user-1")
        self.assertEqual(len(checkpoint.replacement_messages), 1)
        self.assertEqual(result.compaction_state.to_dict()["compacted_history"]["checkpoint_count"], 1)
```

- [x] **Step 2: Run restore test and verify it fails because session has no helper**

Run:

```bash
uv run pytest tests/test_session_restore.py::TestSessionRestorer::test_restore_replays_valid_compacted_history_checkpoint -q
```

Expected:

```text
AttributeError: 'Session' object has no attribute 'latest_compacted_history'
```

- [x] **Step 3: Add compacted-history state to `Session`**

Modify `src/embedagent/session.py` imports:

```python
from embedagent.compacted_history import CompactedHistoryCheckpoint
```

Add to `Session`:

```python
    compacted_history: List[CompactedHistoryCheckpoint] = field(default_factory=list)
```

Add methods:

```python
    def record_compacted_history(self, checkpoint: CompactedHistoryCheckpoint) -> None:
        checkpoint_id = str(getattr(checkpoint, "checkpoint_id", "") or "").strip()
        if not checkpoint_id:
            return
        self.compacted_history = [
            item
            for item in self.compacted_history
            if str(getattr(item, "checkpoint_id", "") or "") != checkpoint_id
        ]
        self.compacted_history.append(checkpoint)

    def latest_compacted_history(self) -> Optional[CompactedHistoryCheckpoint]:
        if not self.compacted_history:
            return None
        return self.compacted_history[-1]
```

- [x] **Step 4: Add restore replay logic**

Modify `src/embedagent/session_restore.py` imports:

```python
from embedagent.compacted_history import CompactedHistoryReducer
```

Add a branch before `loop_transition` handling:

```python
            if event_type == "compacted_history":
                reduced = CompactedHistoryReducer().reduce([event])
                checkpoint = reduced.latest_checkpoint
                if checkpoint is None:
                    if _maybe_skip("compacted_history_invalid"):
                        continue
                    break
                if not self._is_valid_compacted_history(session, checkpoint):
                    if _maybe_skip("compacted_history_invalid_anchor"):
                        continue
                    break
                if checkpoint.checkpoint_id in seen_compacted_history_ids:
                    if _maybe_skip("duplicate_compacted_history_id"):
                        continue
                    break
                session.record_compacted_history(checkpoint)
                seen_compacted_history_ids.add(checkpoint.checkpoint_id)
                continue
```

Initialize near `seen_boundary_ids`:

```python
        seen_compacted_history_ids = set()
```

Add helper:

```python
    def _is_valid_compacted_history(self, session: Session, checkpoint: Any) -> bool:
        if not str(getattr(checkpoint, "checkpoint_id", "") or "").strip():
            return False
        if not list(getattr(checkpoint, "replacement_messages", []) or []):
            return False
        first_kept = str(getattr(checkpoint, "first_kept_message_id", "") or "").strip()
        if first_kept and self._message_index(session, first_kept) < 0:
            return False
        for message in list(getattr(checkpoint, "replacement_messages", []) or []):
            role = str((message or {}).get("role") or "").strip()
            content = str((message or {}).get("content") or "").strip()
            if role not in ("system", "user", "assistant"):
                return False
            if not content:
                return False
        return True
```

- [x] **Step 5: Run valid restore test**

Run:

```bash
uv run pytest tests/test_session_restore.py::TestSessionRestorer::test_restore_replays_valid_compacted_history_checkpoint -q
```

Expected:

```text
1 passed
```

- [x] **Step 6: Add invalid anchor and duplicate tests**

Add to `tests/test_session_restore.py`:

```python
    def test_restore_rejects_compacted_history_with_missing_first_kept_anchor(self):
        events = self._build_valid_transcript()
        events.append(
            {
                "schema_version": 2,
                "session_id": "sess-test",
                "event_id": "evt-4",
                "seq": 4,
                "ts": "2026-06-20T00:00:00Z",
                "type": "compacted_history",
                "payload": {
                    "checkpoint_id": "ch-bad-anchor",
                    "summary_text": "Bad anchor",
                    "first_kept_message_id": "m-missing",
                    "replacement_messages": [{"role": "system", "content": "Bad anchor"}],
                },
            }
        )

        result = SessionRestorer().restore(events, best_effort=True)

        self.assertIsNone(result.session.latest_compacted_history())
        self.assertEqual(result.skipped_count, 1)
        self.assertIn("compacted_history_invalid_anchor", result.skip_reasons[0]["reason"])

    def test_restore_rejects_duplicate_compacted_history_id(self):
        events = self._build_valid_transcript()
        payload = {
            "checkpoint_id": "ch-dup",
            "summary_text": "Summary",
            "first_kept_message_id": "m-user-1",
            "replacement_messages": [{"role": "system", "content": "Summary"}],
        }
        events.append(
            {
                "schema_version": 2,
                "session_id": "sess-test",
                "event_id": "evt-4",
                "seq": 4,
                "ts": "2026-06-20T00:00:00Z",
                "type": "compacted_history",
                "payload": dict(payload),
            }
        )
        events.append(
            {
                "schema_version": 2,
                "session_id": "sess-test",
                "event_id": "evt-5",
                "seq": 5,
                "ts": "2026-06-20T00:00:01Z",
                "type": "compacted_history",
                "payload": dict(payload),
            }
        )

        result = SessionRestorer().restore(events, best_effort=True)

        self.assertEqual(len(result.session.compacted_history), 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertIn("duplicate_compacted_history_id", result.skip_reasons[0]["reason"])
```

- [x] **Step 7: Run restore compacted-history tests**

Run:

```bash
uv run pytest tests/test_session_restore.py -k compacted_history -q
```

Expected:

```text
3 passed
```

## Task 3: Emit Compacted-History Events Without Changing Context Selection

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `tests/test_query_engine_refactor.py`

- [x] **Step 1: Write live emission test**

Extend `test_query_engine_persists_compact_boundary_event_for_restore` in `tests/test_query_engine_refactor.py` after the compact-boundary assertions:

```python
        compacted_history_events = [
            item for item in events if item["type"] == "compacted_history"
        ]
        self.assertEqual(len(compacted_history_events), 1)
        history_payload = compacted_history_events[0]["payload"]
        self.assertTrue(history_payload["checkpoint_id"].startswith("ch-"))
        self.assertEqual(history_payload["boundary_id"], boundary.boundary_id)
        self.assertEqual(history_payload["summary_text"], boundary.summary_text)
        self.assertEqual(
            history_payload["first_kept_message_id"],
            boundary.preserved_head_message_id,
        )
        self.assertEqual(history_payload["replacement_messages"][0]["role"], "system")
        self.assertIn(boundary.summary_text, history_payload["replacement_messages"][0]["content"])
        self.assertEqual(history_payload["trigger"], compact_payload["trigger"])
        self.assertEqual(history_payload["phase"], compact_payload["phase"])
        self.assertEqual(history_payload["token_counts"], compact_payload["token_counts"])
        self.assertEqual(history_payload["message_counts"], compact_payload["message_counts"])
```

- [x] **Step 2: Run the live emission test and verify it fails**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_persists_compact_boundary_event_for_restore -q
```

Expected:

```text
AssertionError: 0 != 1
```

- [x] **Step 3: Add compacted-history payload builder**

Modify `src/embedagent/query_engine.py`:

```python
    def _compacted_history_payload(
        self,
        boundary: Any,
        assembly: ContextAssemblyResult,
        window_state: ContextWindowState,
        token_counts: Dict[str, int],
        message_counts: Dict[str, int],
        file_activity: Dict[str, List[str]],
        evidence_refs: List[str],
    ) -> Dict[str, Any]:
        checkpoint_id = "ch-" + uuid.uuid4().hex[:12]
        replacement_message = {
            "role": "system",
            "content": "Compacted history summary:\n%s" % str(boundary.summary_text or ""),
            "kind": "compacted_history_summary",
            "metadata": {
                "checkpoint_id": checkpoint_id,
                "boundary_id": str(boundary.boundary_id or ""),
            },
        }
        return {
            "checkpoint_id": checkpoint_id,
            "boundary_id": str(boundary.boundary_id or ""),
            "summary_text": str(boundary.summary_text or ""),
            "first_kept_message_id": str(boundary.preserved_head_message_id or ""),
            "replacement_messages": [replacement_message],
            "trigger": window_state.trigger,
            "phase": window_state.phase,
            "token_counts": dict(token_counts),
            "message_counts": dict(message_counts),
            "file_activity": dict(file_activity),
            "evidence_refs": list(evidence_refs),
            "extension_summary": False,
            "created_at": str(boundary.created_at or ""),
            "metadata": {
                "pipeline_steps": list(getattr(assembly, "pipeline_steps", []) or []),
                "source_boundary_id": str(boundary.boundary_id or ""),
            },
        }
```

If `uuid` is not already imported in `query_engine.py`, add:

```python
import uuid
```

- [x] **Step 4: Emit and record the checkpoint after `compact_boundary`**

In `_maybe_record_compact_boundary`, after `_append_transcript_event(..., "compact_boundary", ...)`, add:

```python
            compacted_history_payload = self._compacted_history_payload(
                boundary,
                assembly,
                window_state,
                token_counts,
                message_counts,
                file_activity,
                evidence_refs,
            )
            reduced = CompactedHistoryReducer().reduce(
                [
                    {
                        "type": "compacted_history",
                        "payload": compacted_history_payload,
                    }
                ]
            )
            checkpoint = reduced.latest_checkpoint
            if checkpoint is not None:
                session.record_compacted_history(checkpoint)
                self._append_transcript_event(
                    session,
                    "compacted_history",
                    compacted_history_payload,
                )
```

Add import:

```python
from embedagent.compacted_history import CompactedHistoryReducer
```

- [x] **Step 5: Run live emission test**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_persists_compact_boundary_event_for_restore -q
```

Expected:

```text
1 passed
```

- [x] **Step 6: Run compact/restore focused tests**

Run:

```bash
uv run pytest tests/test_compacted_history.py tests/test_compaction_state.py tests/test_session_restore.py -k "compact or compacted_history" tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_persists_compact_boundary_event_for_restore -q
```

Expected:

```text
passed
```

## Task 4: Extract Deterministic Compactor Interface

**Files:**
- Create: `src/embedagent/compactor.py`
- Modify: `src/embedagent/query_engine.py`
- Create: `tests/test_compactor.py`

- [x] **Step 1: Write tests for deterministic replacement-history construction**

Create `tests/test_compactor.py`:

```python
import unittest

from embedagent.compactor import DeterministicCompactor


class TestDeterministicCompactor(unittest.TestCase):
    def test_build_checkpoint_payload_from_boundary_inputs(self):
        compactor = DeterministicCompactor()
        payload = compactor.build_checkpoint_payload(
            boundary_id="cb-1",
            summary_text="Earlier work",
            created_at="2026-06-20T00:00:00Z",
            first_kept_message_id="m-kept",
            trigger="auto_threshold",
            phase="pre_provider",
            token_counts={"approx_before": 100, "approx_after": 50},
            message_counts={"before": 8, "after": 3, "summarized_turns": 5},
            file_activity={"read_files": ["src/a.c"], "modified_files": []},
            evidence_refs=["ref-a"],
            metadata={"pipeline_steps": ["auto_compact_threshold"]},
        )

        self.assertTrue(payload["checkpoint_id"].startswith("ch-"))
        self.assertEqual(payload["boundary_id"], "cb-1")
        self.assertEqual(payload["summary_text"], "Earlier work")
        self.assertEqual(payload["first_kept_message_id"], "m-kept")
        self.assertEqual(payload["replacement_messages"][0]["role"], "system")
        self.assertIn("Earlier work", payload["replacement_messages"][0]["content"])
        self.assertEqual(payload["token_counts"]["approx_after"], 50)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run compactor test and verify it fails because module is missing**

Run:

```bash
uv run pytest tests/test_compactor.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'embedagent.compactor'
```

- [x] **Step 3: Implement `DeterministicCompactor`**

Create `src/embedagent/compactor.py`:

```python
from __future__ import annotations

import uuid
from typing import Any, Dict, List


class DeterministicCompactor(object):
    def build_checkpoint_payload(
        self,
        boundary_id: str,
        summary_text: str,
        created_at: str,
        first_kept_message_id: str,
        trigger: str,
        phase: str,
        token_counts: Dict[str, int],
        message_counts: Dict[str, int],
        file_activity: Dict[str, List[str]],
        evidence_refs: List[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        checkpoint_id = "ch-" + uuid.uuid4().hex[:12]
        replacement_message = {
            "role": "system",
            "content": "Compacted history summary:\n%s" % str(summary_text or ""),
            "kind": "compacted_history_summary",
            "metadata": {
                "checkpoint_id": checkpoint_id,
                "boundary_id": str(boundary_id or ""),
            },
        }
        return {
            "checkpoint_id": checkpoint_id,
            "boundary_id": str(boundary_id or ""),
            "summary_text": str(summary_text or ""),
            "first_kept_message_id": str(first_kept_message_id or ""),
            "replacement_messages": [replacement_message],
            "trigger": str(trigger or ""),
            "phase": str(phase or ""),
            "token_counts": dict(token_counts or {}),
            "message_counts": dict(message_counts or {}),
            "file_activity": dict(file_activity or {}),
            "evidence_refs": list(evidence_refs or []),
            "extension_summary": False,
            "created_at": str(created_at or ""),
            "metadata": dict(metadata or {}),
        }
```

- [x] **Step 4: Run compactor tests**

Run:

```bash
uv run pytest tests/test_compactor.py -q
```

Expected:

```text
1 passed
```

- [x] **Step 5: Replace QueryEngine helper with the compactor**

Modify `src/embedagent/query_engine.py` to import:

```python
from embedagent.compactor import DeterministicCompactor
```

In `QueryEngine.__init__`, add:

```python
        self.compactor = DeterministicCompactor()
```

Replace `_compacted_history_payload(...)` body with a call to:

```python
        return self.compactor.build_checkpoint_payload(
            boundary_id=str(boundary.boundary_id or ""),
            summary_text=str(boundary.summary_text or ""),
            created_at=str(boundary.created_at or ""),
            first_kept_message_id=str(boundary.preserved_head_message_id or ""),
            trigger=window_state.trigger,
            phase=window_state.phase,
            token_counts=token_counts,
            message_counts=message_counts,
            file_activity=file_activity,
            evidence_refs=evidence_refs,
            metadata={
                "pipeline_steps": list(getattr(assembly, "pipeline_steps", []) or []),
                "source_boundary_id": str(boundary.boundary_id or ""),
            },
        )
```

- [x] **Step 6: Run compactor and query-engine compact tests**

Run:

```bash
uv run pytest tests/test_compactor.py tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_persists_compact_boundary_event_for_restore -q
```

Expected:

```text
passed
```

## Task 5: Context Assembly From Replacement History

**Files:**
- Modify: `src/embedagent/context.py`
- Modify: `src/embedagent/session_restore.py`
- Modify: `tests/test_context_config.py`

- [x] **Step 1: Write context assembly test using a checkpoint**

Add to `tests/test_context_config.py`:

```python
    def test_build_messages_uses_latest_compacted_history_checkpoint_as_base(self):
        from embedagent.compacted_history import CompactedHistoryCheckpoint

        manager = ContextManager()
        session = Session(session_id="sess-checkpoint-context")
        session.add_system_message("mode: build", message_id="m-system")
        session.add_user_message("old user", turn_id="turn-old", message_id="m-old-user")
        session.add_assistant_reply(
            AssistantReply(content="old assistant", actions=[], finish_reason="stop"),
            message_id="m-old-assistant",
        )
        session.add_user_message("new user", turn_id="turn-new", message_id="m-new-user")
        session.record_compacted_history(
            CompactedHistoryCheckpoint(
                checkpoint_id="ch-ctx",
                summary_text="Old work was compacted.",
                first_kept_message_id="m-new-user",
                replacement_messages=[
                    {
                        "role": "system",
                        "content": "Compacted history summary:\nOld work was compacted.",
                        "kind": "compacted_history_summary",
                    }
                ],
            )
        )

        result = manager.build_messages(session, mode_name="build")
        contents = [item.get("content") for item in result.messages]

        self.assertIn("Compacted history summary:\nOld work was compacted.", contents)
        self.assertIn("new user", contents)
        self.assertNotIn("old user", contents)
        self.assertNotIn("old assistant", contents)
        self.assertIn("compacted_history_checkpoint", result.pipeline_steps)
```

- [x] **Step 2: Run the context assembly test and verify it fails**

Run:

```bash
uv run pytest tests/test_context_config.py -k compacted_history_checkpoint -q
```

Expected:

```text
AssertionError: 'old user' unexpectedly found
```

- [x] **Step 3: Add checkpoint slicing helper to `ContextManager`**

Modify `src/embedagent/context.py`:

```python
    def _latest_compacted_history(self, session: Session) -> Any:
        latest = getattr(session, "latest_compacted_history", None)
        if not callable(latest):
            return None
        checkpoint = latest()
        if checkpoint is None:
            return None
        if not list(getattr(checkpoint, "replacement_messages", []) or []):
            return None
        return checkpoint

    def _messages_after_first_kept(self, session: Session, first_kept_message_id: str) -> List[Any]:
        target = str(first_kept_message_id or "").strip()
        if not target:
            return []
        for index, message in enumerate(list(getattr(session, "messages", []) or [])):
            if str(getattr(message, "message_id", "") or "") == target:
                return list(session.messages[index:])
        return []
```

- [x] **Step 4: Use checkpoint base before legacy compact boundary slicing**

At the beginning of `build_messages`, after computing `policy`, add:

```python
        compacted_history = self._latest_compacted_history(session)
        if compacted_history is not None:
            suffix_messages = self._messages_after_first_kept(
                session,
                getattr(compacted_history, "first_kept_message_id", ""),
            )
            if suffix_messages:
                messages = []
                latest_system = self._latest_system_message(session)
                if latest_system is not None:
                    messages.append(self._compact_system_message(latest_system, policy))
                messages.extend(
                    [dict(item) for item in list(compacted_history.replacement_messages or [])]
                )
                messages.extend([self._compact_message(message, policy) for message in suffix_messages])
                used_chars = self._measure_messages(messages)
                budget = self._budget_for_chars(policy, used_chars)
                stats = ContextStats(
                    mode_name=resolved_mode,
                    total_session_messages=len(session.messages),
                    selected_messages=len(messages),
                    total_turns=len(session.turns),
                    recent_turns=0,
                    summarized_turns=int(
                        getattr(compacted_history, "message_counts", {}).get(
                            "summarized_turns", 0
                        )
                        if isinstance(getattr(compacted_history, "message_counts", {}), dict)
                        else 0
                    ),
                    summarized_observations=0,
                    reduced_tool_messages=0,
                    characters_before=self._measure_messages(
                        [message.to_api_dict() for message in session.messages]
                    ),
                    characters_after=used_chars,
                    approx_tokens_before=self._estimate_tokens(
                        self._measure_messages(
                            [message.to_api_dict() for message in session.messages]
                        )
                    ),
                    approx_tokens_after=budget.input_tokens,
                    dropped_messages=max(0, len(session.messages) - len(suffix_messages)),
                    recent_window_shrinks=0,
                    hard_trimmed=False,
                    summary_message_included=True,
                    project_memory_included=False,
                )
                return ContextBuildResult(
                    messages,
                    used_chars,
                    budget.input_tokens,
                    used_chars < stats.characters_before,
                    stats.summarized_turns,
                    stats.recent_turns,
                    policy,
                    budget,
                    stats,
                    summary_message=str(getattr(compacted_history, "summary_text", "") or ""),
                    intelligence_sections=[],
                    analysis=self._analyze_context(session),
                    replacements=[],
                    pipeline_steps=[
                        "compacted_history_checkpoint",
                        "working_set",
                        "prompt_render",
                    ],
                )
```

Keep this initial implementation intentionally simple. Add project memory and workspace intelligence reinjection in a later refinement only if existing tests require it.

- [x] **Step 5: Run context assembly checkpoint test**

Run:

```bash
uv run pytest tests/test_context_config.py -k compacted_history_checkpoint -q
```

Expected:

```text
1 passed
```

- [x] **Step 6: Add restore-to-context test**

Add to `tests/test_session_restore.py`:

```python
    def test_restored_compacted_history_can_drive_context_assembly(self):
        from embedagent.context import ContextManager

        events = self._build_valid_transcript()
        events.append(
            {
                "schema_version": 2,
                "session_id": "sess-test",
                "event_id": "evt-4",
                "seq": 4,
                "ts": "2026-06-20T00:00:00Z",
                "type": "message",
                "payload": {
                    "role": "user",
                    "content": "new work",
                    "message_id": "m-new",
                    "parent_message_id": "m-user-1",
                    "turn_id": "t-2",
                    "step_id": "",
                },
            }
        )
        events.append(
            {
                "schema_version": 2,
                "session_id": "sess-test",
                "event_id": "evt-5",
                "seq": 5,
                "ts": "2026-06-20T00:00:01Z",
                "type": "compacted_history",
                "payload": {
                    "checkpoint_id": "ch-restore-context",
                    "summary_text": "Earlier restored work",
                    "first_kept_message_id": "m-new",
                    "replacement_messages": [
                        {"role": "system", "content": "Compacted history summary:\nEarlier restored work"}
                    ],
                },
            }
        )

        restored = SessionRestorer().restore(events)
        result = ContextManager().build_messages(restored.session, mode_name="build")
        contents = [item.get("content") for item in result.messages]

        self.assertIn("Compacted history summary:\nEarlier restored work", contents)
        self.assertIn("new work", contents)
        self.assertIn("compacted_history_checkpoint", result.pipeline_steps)
```

- [x] **Step 7: Run context and restore suites**

Run:

```bash
uv run pytest tests/test_context_config.py -k "context_plan or compacted_history_checkpoint or auto_compact" tests/test_session_restore.py -k "compacted_history or restored_compacted_history" -q
```

Expected:

```text
passed
```

## Task 6: Documentation And Guard Tests

**Files:**
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/tool-contracts.md`
- Modify: `docs/agent-harness-v2.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/superpowers/plans/2026-06-20-compacted-history-checkpoints.md`

- [x] **Step 1: Update durable docs from future direction to implemented slice**

Update the docs to say:

```text
The current implementation records compacted-history checkpoints as transcript events and reducer diagnostics. Context assembly can use the latest valid checkpoint plus the newer transcript suffix when a checkpoint is available. `CompactionStateReducer` remains diagnostics-only and does not decide permissions, tool activation, extension loading, or frontend policy.
```

Do not remove the existing warnings about reducers staying read-only.

- [x] **Step 2: Add a design-change-log entry**

Add a new `DC-189` entry to `docs/design-change-log.md`:

```markdown
### DC-189

- 日期：2026-06-20
- 变更主题：Compacted-history checkpoint implementation
- 变更摘要：
  - 新增 `compacted_history` transcript event、live session checkpoint state 和 reducer projection。
  - `QueryEngine` 在 compact boundary 后写入 replacement-history checkpoint，保留 `compact_boundary` 兼容事件。
  - `SessionRestorer` 验证 checkpoint id、first-kept anchor 和 replacement message shape 后恢复 checkpoint。
  - `ContextManager` 可从最新有效 checkpoint 加 transcript suffix 构建 provider history。
- 影响范围：
  - Agent Core context/session restore
  - structured compaction diagnostics
  - compact retry transcript replay
- 关联文档：
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/tool-contracts.md`
  - `docs/agent-harness-v2.md`
- 是否需要 ADR：否；这是既有 Pi-inspired compact architecture 的实现切片，不改变 permission engine、tool activation policy 或 session-history truth。
- 后续动作：
  - 继续抽象 provider-generated summary 和 extension-supplied summary，但保留 deterministic local summary fallback。
```

- [x] **Step 3: Run placeholder and stale wording scan**

Run:

```bash
rg -n "T[B]D|T[O]DO|implemented later|future compacted-history only|diagnostic-only compact boundaries" docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/tool-contracts.md docs/agent-harness-v2.md docs/design-change-log.md
```

Expected: no output.

- [x] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_compacted_history.py tests/test_compaction_state.py tests/test_context_config.py tests/test_session_restore.py tests/test_query_engine_refactor.py -k "compact or compacted_history or context_plan" -q
```

Expected:

```text
passed
```

- [x] **Step 5: Run formatting and lint checks**

Result: targeted touched-file `black --check` and `ruff check` passed after formatting. Full-repo `black --check src/ tests/` and `ruff check src/ tests/` still report pre-existing unrelated formatting/import issues outside this slice.

Run:

```bash
uv run black --check src/ tests/
uv run ruff check src/ tests/
```

Expected:

```text
All done!
All checks passed!
```

If these fail on unrelated pre-existing files, do not format unrelated files without a separate cleanup decision. Record the exact unrelated failures in the final status.

- [x] **Step 6: Run final diff review**

Run:

```bash
git diff --check
git diff --stat
```

Expected:

```text
git diff --check exits 0
```

Review the diff stat and confirm changes are limited to the files listed in this plan unless a test-discovered dependency required a documented adjustment.

## Rollout Notes

- Slice 1 and Slice 2 do not change active provider context selection.
- Slice 3 writes the new event but keeps legacy `compact_boundary` for compatibility.
- Slice 4 only extracts construction behind an interface.
- Slice 5 is the behavior change: provider context can use replacement history.
- Legacy compact boundaries must remain readable throughout.
- The deterministic compactor is mandatory. Provider-generated summaries and extension-supplied summaries are later optional strategies.
- No new runtime dependencies, online services, Docker, WSL, VS Code, Node runtime, or Python 3.9+ syntax are allowed.

## Verification Summary Template

Use this when the plan is executed:

```text
Implemented:
- compacted_history reducer projection
- restore/live session checkpoint replay
- QueryEngine checkpoint event emission
- deterministic compactor interface
- context assembly from latest checkpoint plus suffix

Verification:
- uv run pytest tests/test_compacted_history.py tests/test_compaction_state.py tests/test_context_config.py tests/test_session_restore.py tests/test_query_engine_refactor.py -k "compact or compacted_history or context_plan" -q
- uv run black --check src/ tests/
- uv run ruff check src/ tests/
- git diff --check

Known gaps:
- provider-generated summaries are not implemented
- extension-supplied summaries are not implemented
- legacy compact_boundary compatibility remains intentionally supported
```
