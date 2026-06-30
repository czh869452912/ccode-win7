# Interaction Lifecycle Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge permission and `ask_user` into one Core/hosted interaction lifecycle, with Pi-style Agent/TUI ownership and T3 Code-style GUI response semantics.

**Architecture:** `Session.pending_interaction` remains the durable Core truth. Hosted runtime owns one blocking pending ticket and exposes only `respond_to_interaction()`, while GUI/TUI render shell read models and send T3-compatible `decision` or `answers` payloads. Old split pending fields and old public approve/reject/reply APIs are removed after callers and tests move to the unified path.

**Tech Stack:** Python 3.8, FastAPI backend routes, pytest, React webapp JavaScript modules, Node webapp test runner, npm build.

---

## File Structure

- `src/embedagent/session_runtime.py`: Replace split live pending fields with one hosted `pending_interaction`, one wait event, and one response payload.
- `src/embedagent/hosted_interaction_service.py`: Create and resolve the single hosted pending ticket; validate T3-compatible response payloads; update session remember state from backend ticket category.
- `src/embedagent/inprocess_adapter.py`: Project one pending interaction into snapshots, rebuild one hosted ticket from restored Core pending state, release waits on cancel, and expose only `respond_to_interaction()` for product callers.
- `src/embedagent/session_projector.py`: Compute `pending_interaction_valid` from the provided pending payload, not split runtime fields.
- `src/embedagent/hosted_command_service.py`: Use the unified hosted pending wait fields for command-owned permission waits.
- `src/embedagent/core/adapter.py`: Remove product-facing `approve_permission()`, `reject_permission()`, and `reply_user_input()` wrappers.
- `src/embedagent/protocol/__init__.py`: Remove product-facing old response methods from frontend protocol contracts.
- `src/embedagent/frontend/tui/state.py`: Replace `pending_permission` and `pending_user_input` with a single shell `pending_interaction` convenience view.
- `src/embedagent/frontend/tui/reducer.py`: Replace split pending setters with one pending interaction setter/clearer.
- `src/embedagent/frontend/tui/services/sessions.py`: Replace `approve()`, `reject()`, and `reply_user_input()` with `respond_to_interaction()`.
- `src/embedagent/frontend/tui/controller.py`: Turn terminal shortcuts into `decision` and `answers` payloads over the unified response service.
- `src/embedagent/frontend/tui/frontend_adapter.py`: Stop storing raw callback requests as split pending state; derive pending display from snapshots.
- `src/embedagent/frontend/tui/views/*.py`: Render pending state from `state.session.pending_interaction`.
- `src/embedagent/frontend/gui/backend/routes_sessions.py`: Keep only the unified interaction response route and serialize Core-owned responses.
- `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`: Project `questions` for user input and build `decision`/`answers` response payloads.
- `src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js`: Track in-flight responses by request id and log new payload shapes.
- `src/embedagent/frontend/gui/webapp/src/App.jsx`: Replace single global interaction busy string with request-id response tracking and include `waiting_permission` in interruptible status.
- `src/embedagent/frontend/gui/webapp/src/workbench/workbench-parity-model.js`: Treat both waiting statuses as interruptible/running for shell controls.
- `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx`: Split into T3-style approval and user-input panels/actions, or keep the wrapper while delegating to focused subcomponents.
- `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingApprovalPanel.jsx`: New focused approval display.
- `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingApprovalActions.jsx`: New focused approval actions.
- `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingUserInputPanel.jsx`: New focused user-input prompt panel.
- `tests/test_inprocess_adapter_frontend_api.py`: Backend lifecycle regression tests.
- `tests/test_gui_backend_api.py`: Unified route payload tests.
- `tests/test_pre_release_architecture_guards.py`: Deletion guards for old API/state/payload shapes.
- `src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs`: GUI read-model and payload unit tests.
- `src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs`: GUI response controller tests.
- `src/embedagent/frontend/gui/webapp/test/workbench-parity-model.test.mjs`: Waiting permission interruptibility test.
- `src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs`: Source guards for focused composer modules.

## Task 1: Lock Architecture Guards

**Files:**
- Modify: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Add guards for old hosted/session runtime state**

Add this test near the existing interaction/session guards:

```python
def test_hosted_runtime_uses_single_pending_interaction_state():
    files = [
        ROOT / "src/embedagent/session_runtime.py",
        ROOT / "src/embedagent/hosted_interaction_service.py",
        ROOT / "src/embedagent/inprocess_adapter.py",
        ROOT / "src/embedagent/session_projector.py",
        ROOT / "src/embedagent/hosted_command_service.py",
    ]
    forbidden = (
        "state.pending_permission",
        "state.pending_user_input",
        "state.pending_result",
        "state.pending_user_event",
        "state.pending_user_response",
        "pending_permission: Optional",
        "pending_user_input: Optional",
        "pending_result: Optional",
        "pending_user_event: Optional",
        "pending_user_response: Optional",
        "clear_pending_permission(",
        "clear_pending_user_input(",
    )
    offenders = []
    for path in files:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []
```

- [ ] **Step 2: Add guards for old public response APIs**

Add this test below the hosted runtime guard:

```python
def test_product_interfaces_expose_only_unified_interaction_response():
    files = [
        ROOT / "src/embedagent/core/adapter.py",
        ROOT / "src/embedagent/protocol/__init__.py",
        ROOT / "src/embedagent/inprocess_adapter.py",
        ROOT / "src/embedagent/frontend/tui/services/sessions.py",
    ]
    forbidden = (
        "def approve_permission",
        "def reject_permission",
        "def reply_user_input",
        ".approve_permission(",
        ".reject_permission(",
        ".reply_user_input(",
    )
    offenders = []
    for path in files:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []
```

- [ ] **Step 3: Add guards for legacy GUI/TUI payload fields**

Add this test below the public API guard:

```python
def test_shell_interaction_payloads_use_decision_and_answers_contract():
    files = [
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js",
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx",
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js",
        ROOT / "src/embedagent/frontend/tui/controller.py",
    ]
    forbidden = (
        "response_kind",
        "remember:",
        "selected_mode",
        "selected_option_text",
    )
    offenders = []
    for path in files:
        if not path.exists():
            continue
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []

    interaction_model = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js"
    )
    permission_builder = re.search(
        r"function buildPermissionResponse[\s\S]*?}\n",
        interaction_model,
    ) or re.search(
        r"export function buildPermissionResponse[\s\S]*?}\n",
        interaction_model,
    )
    assert permission_builder is not None
    assert "category" not in permission_builder.group(0)
```

- [ ] **Step 4: Run guards and confirm red**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py::test_hosted_runtime_uses_single_pending_interaction_state tests/test_pre_release_architecture_guards.py::test_product_interfaces_expose_only_unified_interaction_response tests/test_pre_release_architecture_guards.py::test_shell_interaction_payloads_use_decision_and_answers_contract -v
```

Expected: FAIL. Current code still contains split hosted pending fields, old public response methods, and legacy GUI payload keys.

- [ ] **Step 5: Commit only the failing guards**

```bash
git add tests/test_pre_release_architecture_guards.py
git commit -m "test: guard unified interaction lifecycle"
```

## Task 2: Converge Hosted Runtime Pending State

**Files:**
- Modify: `src/embedagent/session_runtime.py`
- Modify: `src/embedagent/hosted_interaction_service.py`
- Modify: `src/embedagent/session_projector.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Add backend tests for new pending snapshot shape and payloads**

In `tests/test_inprocess_adapter_frontend_api.py`, update `test_live_user_input_pending_id_matches_session_pending_interaction` to assert `questions`:

```python
self.assertEqual(snapshot_interaction.get("kind"), "user_input")
self.assertIn("questions", snapshot_interaction)
self.assertEqual(snapshot_interaction["questions"][0]["id"], "answer")
self.assertEqual(snapshot_interaction["questions"][0]["question"], "下一步怎么做？")
self.assertEqual(snapshot_interaction["questions"][0]["options"][0]["label"], "切到 debug 模式继续排查")
self.assertEqual(snapshot_interaction["questions"][0]["multi_select"], False)
```

Add this test near the existing pending-id tests:

```python
def test_managed_session_has_one_hosted_pending_interaction_field(self):
    adapter = InProcessAdapter(
        client=AskUserClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    snapshot = adapter.create_session("spec")
    session_id = str(snapshot.get("session_id") or "")

    adapter.submit_user_message(
        session_id=session_id,
        text="请继续",
        stream=False,
        wait=True,
        event_handler=lambda event_name, current_session_id, payload: None,
    )

    state = adapter._sessions[session_id]
    with state.lock:
        self.assertIsNotNone(state.pending_interaction)
        self.assertFalse(hasattr(state, "pending_permission"))
        self.assertFalse(hasattr(state, "pending_user_input"))
        self.assertFalse(hasattr(state, "pending_result"))
        self.assertFalse(hasattr(state, "pending_user_event"))
        self.assertFalse(hasattr(state, "pending_user_response"))
```

- [ ] **Step 2: Run the backend tests and confirm red**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_live_user_input_pending_id_matches_session_pending_interaction tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_managed_session_has_one_hosted_pending_interaction_field -v
```

Expected: FAIL because user input snapshots still expose `question`/`options` and `ManagedSession` still has split fields.

- [ ] **Step 3: Replace `ManagedSession` fields**

In `src/embedagent/session_runtime.py`, remove the `UserInputResponse` import and replace fields:

```python
    pending_interaction: Optional[Any] = None
    pending_event: Optional[threading.Event] = None
    pending_response: Optional[Dict[str, Any]] = None
```

Keep `remembered_permission_categories`, `stop_event`, and `lock` unchanged.

- [ ] **Step 4: Replace hosted ticket dataclasses**

In `src/embedagent/hosted_interaction_service.py`, replace `PermissionTicket` and `UserInputTicket` with:

```python
@dataclass
class HostedPendingInteraction:
    interaction_id: str
    kind: str
    session_id: str
    tool_name: str
    payload: Dict[str, Any]
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "interaction_id": self.interaction_id,
            "kind": self.kind,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "turn_id": self.turn_id,
            "step_id": self.step_id,
            "step_index": self.step_index,
            "created_at": self.created_at,
        }
        result.update(dict(self.payload or {}))
        return result
```

Add `field` to the dataclass import.

- [ ] **Step 5: Add helper functions for payload conversion**

In `hosted_interaction_service.py`, add:

```python
def _request_kind_for_category(category: str) -> str:
    value = str(category or "").strip()
    if value == "read":
        return "file-read"
    if value in ("workspace_write", "git_write"):
        return "file-change"
    return "command"


def _questions_for_request(request: UserInputRequest) -> Dict[str, Any]:
    options = []
    for item in request.options:
        options.append(
            {
                "label": item.text,
                "description": item.text,
                "value": item.text,
                "index": item.index,
                "mode": item.mode,
            }
        )
    return {
        "questions": [
            {
                "id": "answer",
                "question": request.question,
                "options": options,
                "multi_select": False,
            }
        ],
        "details": _public_details(request.details),
    }
```

- [ ] **Step 6: Update ticket creation**

Change `create_permission_ticket()` to set `state.pending_interaction = ticket` and `state.pending_response = None`. Build payload:

```python
payload={
    "category": request.category,
    "reason": request.reason,
    "details": _public_details(request.details),
    "request_kind": _request_kind_for_category(request.category),
}
```

Change `create_user_input_ticket()` to set `state.pending_interaction = ticket` and `state.pending_response = None`, with payload from `_questions_for_request(request)`.

- [ ] **Step 7: Replace clear helpers**

Replace `clear_pending_permission()` and `clear_pending_user_input()` with:

```python
def clear_pending_interaction(self, state: ManagedSession) -> None:
    with state.lock:
        state.pending_interaction = None
        state.pending_event = None
        state.pending_response = None
        if state.status != "error":
            state.status = "running"
        state.updated_at = _utc_now()
```

- [ ] **Step 8: Update snapshot projection**

In `src/embedagent/inprocess_adapter.py`, replace `_pending_interaction_payload()` with:

```python
def _pending_interaction_payload(state: "ManagedSession") -> Optional[Dict[str, Any]]:
    pending = getattr(state, "pending_interaction", None)
    if pending is None:
        return None
    to_dict = getattr(pending, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(pending, dict):
        return dict(pending)
    return None
```

In `src/embedagent/session_projector.py`, compute validity from the supplied payload:

```python
"pending_interaction_valid": bool(pending_interaction),
```

- [ ] **Step 9: Update adapter restore path**

In `InProcessAdapter._restore_managed_state` or the local block that rebuilds pending state from `session.pending_interaction`, assign one `HostedPendingInteraction` through `HostedInteractionService` helpers or a new `rebuild_pending_ticket_from_core(state)` method. Preserve the Core interaction id exactly.

Expected permission snapshot fields:

```python
{
    "interaction_id": interaction_id,
    "kind": "permission",
    "category": category,
    "reason": reason,
    "details": details,
    "request_kind": request_kind,
}
```

Expected user-input snapshot fields:

```python
{
    "interaction_id": interaction_id,
    "kind": "user_input",
    "questions": [...],
    "details": details,
}
```

- [ ] **Step 10: Update immediate resolver clears**

Replace calls to `self.interaction_service.clear_pending_permission(state)` and `clear_pending_user_input(state)` in `inprocess_adapter.py` with `clear_pending_interaction(state)`.

- [ ] **Step 11: Run tests and guards**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_live_user_input_pending_id_matches_session_pending_interaction tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_managed_session_has_one_hosted_pending_interaction_field tests/test_pre_release_architecture_guards.py::test_hosted_runtime_uses_single_pending_interaction_state -v
```

Expected: PASS for the two backend tests and the hosted runtime guard.

- [ ] **Step 12: Commit**

```bash
git add src/embedagent/session_runtime.py src/embedagent/hosted_interaction_service.py src/embedagent/session_projector.py src/embedagent/inprocess_adapter.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "refactor: converge hosted pending interaction state"
```

## Task 3: Implement Unified Response Semantics

**Files:**
- Modify: `src/embedagent/hosted_interaction_service.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/hosted_command_service.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`
- Test: `tests/test_gui_backend_api.py`

- [ ] **Step 1: Update ask_user response test to use `answers`**

In `test_respond_to_interaction_emits_ask_user_tool_finish_and_completes_pending`, replace the old payload with:

```python
adapter.respond_to_interaction(
    session_id,
    interaction_id,
    {"answers": {"answer": "切到 debug 模式继续排查"}},
)
```

Keep assertions for `selected_mode == "debug"` and `current_mode == "debug"` so the backend must derive mode from the hosted ticket.

- [ ] **Step 2: Replace old permission approval test with unified accept**

Rename `test_approve_permission_returns_resolved_snapshot_for_command_wait` to `test_permission_accept_decision_returns_resolved_snapshot_for_command_wait` and replace:

```python
resolved = adapter.approve_permission(session_id, permission_id)
```

with:

```python
resolved = adapter.respond_to_interaction(
    session_id,
    permission_id,
    {"decision": "accept"},
)
```

Assert:

```python
self.assertEqual(resolved["status"], "idle")
self.assertFalse(resolved["pending_interaction_valid"])
self.assertIsNone(resolved.get("pending_interaction"))
```

- [ ] **Step 3: Add acceptForSession regression test**

Add this test near the permission wait tests:

```python
def test_permission_accept_for_session_remembers_backend_ticket_category(self):
    os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
    with open(
        os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write(
            '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
        )
    adapter = InProcessAdapter(
        client=FakeClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
    )
    snapshot = adapter.create_session("build")
    session_id = str(snapshot.get("session_id") or "")
    worker = threading.Thread(
        target=adapter.submit_user_message,
        kwargs={
            "session_id": session_id,
            "text": "/run custom.build",
            "stream": False,
            "wait": True,
            "event_handler": lambda event_name, current_session_id, payload: None,
        },
    )
    worker.start()
    deadline = time.time() + 3.0
    waiting = adapter.get_session_snapshot(session_id)
    while time.time() < deadline:
        waiting = adapter.get_session_snapshot(session_id)
        if waiting.get("status") == "waiting_permission":
            break
        time.sleep(0.05)
    pending = waiting.get("pending_interaction") or {}
    self.assertEqual(pending.get("kind"), "permission")
    self.assertEqual(pending.get("category"), "toolchain_exec")
    interaction_id = str(pending.get("interaction_id") or "")
    self.assertTrue(interaction_id)

    adapter.respond_to_interaction(session_id, interaction_id, {"decision": "acceptForSession"})
    worker.join(3.0)

    context = adapter.get_permission_context(session_id)
    self.assertIn("toolchain_exec", context.get("remembered_categories") or [])
```

- [ ] **Step 4: Add invalid/stale response tests**

Add:

```python
def test_respond_to_interaction_rejects_legacy_payload_shape(self):
    adapter = InProcessAdapter(
        client=AskUserClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    snapshot = adapter.create_session("spec")
    session_id = str(snapshot.get("session_id") or "")
    adapter.submit_user_message(
        session_id=session_id,
        text="请继续",
        stream=False,
        wait=True,
        event_handler=lambda event_name, current_session_id, payload: None,
    )
    waiting = adapter.get_session_snapshot(session_id)
    interaction_id = str((waiting.get("pending_interaction") or {}).get("interaction_id") or "")

    with self.assertRaises(ValueError) as raised:
        adapter.respond_to_interaction(
            session_id,
            interaction_id,
            {"response_kind": "answer", "answer": "legacy"},
        )
    self.assertIn("invalid_interaction_response", str(raised.exception))
```

And:

```python
def test_respond_to_interaction_conflicts_when_another_pending_is_active(self):
    adapter = InProcessAdapter(
        client=AskUserClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=True, workspace=self.workspace),
    )
    snapshot = adapter.create_session("spec")
    session_id = str(snapshot.get("session_id") or "")
    adapter.submit_user_message(
        session_id=session_id,
        text="请继续",
        stream=False,
        wait=True,
        event_handler=lambda event_name, current_session_id, payload: None,
    )

    with self.assertRaises(ValueError) as raised:
        adapter.respond_to_interaction(
            session_id,
            "different-id",
            {"answers": {"answer": "x"}},
        )
    self.assertIn("interaction_conflict", str(raised.exception))
```

- [ ] **Step 5: Add permission cancel regression test**

Add this test near the permission response tests:

```python
def test_permission_cancel_decision_interrupts_pending_wait(self):
    os.makedirs(os.path.join(self.workspace, ".embedagent"), exist_ok=True)
    with open(
        os.path.join(self.workspace, ".embedagent", "workspace-recipes.json"),
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write(
            '[{"id":"custom.build","tool_name":"run_recipe","recipe_action":"build","label":"Custom Build","command":"cmd /c echo build-ok","cwd":"."}]'
        )
    adapter = InProcessAdapter(
        client=FakeClient(),
        tools=self.tools,
        permission_policy=PermissionPolicy(auto_approve_all=False, workspace=self.workspace),
    )
    snapshot = adapter.create_session("build")
    session_id = str(snapshot.get("session_id") or "")
    worker = threading.Thread(
        target=adapter.submit_user_message,
        kwargs={
            "session_id": session_id,
            "text": "/run custom.build",
            "stream": False,
            "wait": True,
            "event_handler": lambda event_name, current_session_id, payload: None,
        },
    )
    worker.start()
    deadline = time.time() + 3.0
    waiting = adapter.get_session_snapshot(session_id)
    while time.time() < deadline:
        waiting = adapter.get_session_snapshot(session_id)
        if waiting.get("status") == "waiting_permission":
            break
        time.sleep(0.05)
    interaction_id = str((waiting.get("pending_interaction") or {}).get("interaction_id") or "")
    self.assertTrue(interaction_id)

    resolved = adapter.respond_to_interaction(session_id, interaction_id, {"decision": "cancel"})

    worker.join(3.0)
    self.assertFalse(worker.is_alive())
    final_snapshot = adapter.get_session_snapshot(session_id)
    self.assertFalse(final_snapshot["pending_interaction_valid"])
    self.assertIsNone(final_snapshot.get("pending_interaction"))
    self.assertIn(resolved["status"], ("idle", "running"))
```

- [ ] **Step 6: Run tests and confirm red**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_respond_to_interaction_emits_ask_user_tool_finish_and_completes_pending tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_permission_accept_decision_returns_resolved_snapshot_for_command_wait tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_permission_accept_for_session_remembers_backend_ticket_category tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_respond_to_interaction_rejects_legacy_payload_shape tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_respond_to_interaction_conflicts_when_another_pending_is_active tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_permission_cancel_decision_interrupts_pending_wait -v
```

Expected: FAIL because `respond_to_interaction()` still expects `response_kind` and calls old helper branches.

- [ ] **Step 7: Implement response validation helpers**

In `hosted_interaction_service.py`, add:

```python
_PERMISSION_DECISIONS = set(["accept", "acceptForSession", "decline", "cancel"])


def _invalid_response() -> ValueError:
    return ValueError("invalid_interaction_response")


def _answer_from_payload(payload: Dict[str, Any]) -> str:
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        raise _invalid_response()
    if "answer" in answers:
        return str(answers.get("answer") or "")
    if answers:
        first_key = sorted(answers.keys())[0]
        return str(answers.get(first_key) or "")
    raise _invalid_response()
```

- [ ] **Step 8: Implement option matching**

Add:

```python
def _response_for_answer(ticket: HostedPendingInteraction, answer: str) -> UserInputResponse:
    questions = ticket.payload.get("questions") or []
    options = []
    if questions and isinstance(questions[0], dict):
        options = list(questions[0].get("options") or [])
    for item in options:
        if not isinstance(item, dict):
            continue
        if str(item.get("label") or item.get("value") or "") == answer:
            return UserInputResponse(
                answer=answer,
                selected_index=item.get("index"),
                selected_mode=str(item.get("mode") or ""),
                selected_option_text=str(item.get("label") or answer),
            )
    return UserInputResponse(answer=answer)
```

- [ ] **Step 9: Rewrite `respond_to_interaction()`**

Make `respond_to_interaction()`:

1. Require the current hosted `state.pending_interaction`.
2. If no pending exists, raise `ValueError("interaction_expired")`.
3. If pending id differs, raise `ValueError("interaction_conflict")`.
4. For permission:
   - require `decision` in `_PERMISSION_DECISIONS`;
   - `acceptForSession` stores `ticket.payload["category"]`;
   - `accept` and `acceptForSession` set `pending_response = {"approved": True}`;
   - `decline` sets `pending_response = {"approved": False}`;
   - `cancel` sets `state.stop_event`, sets `pending_response = {"cancelled": True, "approved": False}`, releases `pending_event`, and returns a fresh snapshot after the active wait clears.
5. For user input:
   - require `answers`;
   - map to `UserInputResponse`;
   - set `pending_response` as `{"user_input": response}` for command wait or run-turn resume payload for Core pending resume.

Return:

```python
{
    "session_id": session_id,
    "interaction_id": interaction_id,
    "status": "resolved",
    "snapshot": self._get_session_snapshot(session_id),
}
```

- [ ] **Step 10: Preserve command wait behavior**

When `state.pending_event` exists, set `state.pending_response` and `state.pending_event.set()`, then call `wait_for_command_resolution(session_id)` and return the snapshot. This replaces `pending_result` and `pending_user_response`.

- [ ] **Step 11: Update cancel wait behavior**

For permission `decision: "cancel"` while `state.pending_event` exists:

```python
with state.lock:
    state.stop_event.set()
    state.pending_response = {"cancelled": True, "approved": False}
    event = state.pending_event
if event is not None:
    event.set()
snapshot = self.wait_for_command_resolution(session_id)
self.clear_pending_interaction(state)
return {
    "session_id": session_id,
    "interaction_id": interaction_id,
    "status": "resolved",
    "snapshot": snapshot,
}
```

This mirrors Pi's session-owned abort path and avoids treating cancel as an affirmative permission response.

- [ ] **Step 12: Update non-command Core resume**

For permission resume, call `_run_turn(..., interaction_resolution={"approved": approved}, resume_pending=True)`.

For user-input resume, call `_run_turn(..., interaction_resolution={"answer": response.answer, "selected_index": response.selected_index, "selected_mode": response.selected_mode, "selected_option_text": response.selected_option_text}, resume_pending=True)`.

- [ ] **Step 13: Update `hosted_command_service.py` wait read**

Replace:

```python
approved = bool(state.pending_result)
state.pending_result = None
```

with:

```python
response = dict(state.pending_response or {})
if response.get("cancelled"):
    state.stop_event.set()
approved = bool(response.get("approved"))
state.pending_response = None
```

- [ ] **Step 14: Update route error mapping if needed**

In `src/embedagent/frontend/gui/backend/http_errors.py`, ensure these strings map as expected:

- `interaction_expired` -> 410
- `interaction_conflict` -> 409
- `invalid_interaction_response` -> 422

- [ ] **Step 15: Run targeted tests**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_respond_to_interaction_emits_ask_user_tool_finish_and_completes_pending tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_permission_accept_decision_returns_resolved_snapshot_for_command_wait tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_permission_accept_for_session_remembers_backend_ticket_category tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_respond_to_interaction_rejects_legacy_payload_shape tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_respond_to_interaction_conflicts_when_another_pending_is_active tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_permission_cancel_decision_interrupts_pending_wait -v
```

Expected: PASS.

- [ ] **Step 16: Commit**

```bash
git add src/embedagent/hosted_interaction_service.py src/embedagent/inprocess_adapter.py src/embedagent/hosted_command_service.py src/embedagent/frontend/gui/backend/http_errors.py tests/test_inprocess_adapter_frontend_api.py
git commit -m "feat: resolve interactions through unified payloads"
```

## Task 4: Delete Old Product APIs And Migrate TUI

**Files:**
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `src/embedagent/protocol/__init__.py`
- Modify: `src/embedagent/frontend/tui/state.py`
- Modify: `src/embedagent/frontend/tui/reducer.py`
- Modify: `src/embedagent/frontend/tui/services/sessions.py`
- Modify: `src/embedagent/frontend/tui/controller.py`
- Modify: `src/embedagent/frontend/tui/frontend_adapter.py`
- Modify: `src/embedagent/frontend/tui/app.py`
- Modify: `src/embedagent/frontend/tui/views/composer.py`
- Modify: `src/embedagent/frontend/tui/views/dialogs.py`
- Modify: `src/embedagent/frontend/tui/views/header.py`
- Modify: `src/embedagent/frontend/tui/views/inspector.py`
- Test: `tests/test_pre_release_architecture_guards.py`

- [ ] **Step 1: Update TUI state**

In `src/embedagent/frontend/tui/state.py`, replace:

```python
pending_permission: Optional[Dict[str, Any]] = None
pending_user_input: Optional[Dict[str, Any]] = None
```

with:

```python
pending_interaction: Optional[Dict[str, Any]] = None
```

- [ ] **Step 2: Update reducer**

In `src/embedagent/frontend/tui/reducer.py`, replace split clear and setters with:

```python
def reset_session_buffers(state: TerminalState) -> None:
    state.timeline.lines = []
    state.timeline.stream_text = ""
    state.timeline.follow_output = True
    state.session.pending_interaction = None
    state.session.last_context_event = {}
    state.session.last_error = ""
    state.preview_path = ""
    state.preview_text = ""
    state.editor = state.editor.__class__()
    state.main_view = "timeline"
    state.inspector.tab = "status"


def set_pending_interaction(state: TerminalState, ticket: Optional[Dict[str, object]]) -> None:
    state.session.pending_interaction = dict(ticket or {}) if ticket else None
```

- [ ] **Step 3: Update TUI session service**

In `src/embedagent/frontend/tui/services/sessions.py`, remove `approve()`, `reject()`, and `reply_user_input()`. Add:

```python
def respond_to_interaction(
    self,
    session_id: str,
    interaction_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return self.adapter.respond_to_interaction(session_id, interaction_id, payload)
```

- [ ] **Step 4: Update controller reply routing**

In `controller.py`, route on one pending interaction:

```python
pending = self.owner.state.session.pending_interaction
if pending is not None:
    if pending.get("kind") == "permission":
        self.handle_permission_reply(text)
    elif pending.get("kind") == "user_input":
        self.handle_user_input_reply(text)
    else:
        reducer.append_line(self.owner.state, "[interaction] unknown pending interaction")
    return
```

- [ ] **Step 5: Update permission shortcuts**

In `handle_permission_reply()`, read:

```python
ticket = self.owner.state.session.pending_interaction or {}
interaction_id = str(ticket.get("interaction_id") or "")
```

Map:

```python
payload = {"decision": "accept"}  # y/yes
payload = {"decision": "decline"}  # n/no
```

Submit:

```python
snapshot = self.owner.session_service.respond_to_interaction(
    self.owner.state.session.current_session_id,
    interaction_id,
    payload,
)
reducer.set_pending_interaction(self.owner.state, None)
reducer.set_snapshot(self.owner.state, snapshot)
```

- [ ] **Step 6: Update user-input shortcuts**

In `handle_user_input_reply()`, read questions:

```python
ticket = self.owner.state.session.pending_interaction or {}
interaction_id = str(ticket.get("interaction_id") or "")
questions = ticket.get("questions") or []
question = questions[0] if questions and isinstance(questions[0], dict) else {}
options = question.get("options") or []
```

Resolve numeric input to an option label, then submit:

```python
snapshot = self.owner.session_service.respond_to_interaction(
    self.owner.state.session.current_session_id,
    interaction_id,
    {"answers": {"answer": answer}},
)
```

- [ ] **Step 7: Update frontend adapter snapshot handling**

In `frontend_adapter.py`, remove `set_pending_permission()` and `set_pending_user_input()` calls from raw callbacks. In `on_session_status_change()`, set:

```python
pending_interaction = snapshot.pending_interaction if snapshot.pending_interaction_valid else None
reducer.set_pending_interaction(self.app.state, pending_interaction)
reducer.update_snapshot(
    self.app.state,
    status=snapshot.status.value,
    current_mode=snapshot.current_mode,
    pending_interaction=pending_interaction,
    pending_interaction_valid=bool(pending_interaction),
)
```

- [ ] **Step 8: Update TUI views**

In each TUI view, replace split checks with:

```python
pending = state.session.pending_interaction
if pending is not None and pending.get("kind") == "permission":
    ...
if pending is not None and pending.get("kind") == "user_input":
    ...
```

For user input display, read `questions[0]["question"]`. For permission display, read `reason`.

- [ ] **Step 9: Delete public wrappers**

Remove `approve_permission()`, `reject_permission()`, and `reply_user_input()` from:

- `src/embedagent/inprocess_adapter.py`
- `src/embedagent/core/adapter.py`
- `src/embedagent/protocol/__init__.py`

Keep `respond_to_interaction()`.

- [ ] **Step 10: Update Python tests still calling old methods**

In `tests/test_inprocess_adapter_frontend_api.py`, replace cleanup calls:

```python
adapter.approve_permission(session_id, permission_id)
```

with:

```python
adapter.respond_to_interaction(session_id, permission_id, {"decision": "accept"})
```

In `tests/test_query_engine_refactor.py`, replace adapter resume calls:

```python
adapter.reply_user_input(session_id, request_id, "answer")
adapter.approve_permission(session_id, permission_id)
```

with:

```python
adapter.respond_to_interaction(session_id, request_id, {"answers": {"answer": "answer"}})
adapter.respond_to_interaction(session_id, permission_id, {"decision": "accept"})
```

- [ ] **Step 11: Run guards and focused tests**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py::test_product_interfaces_expose_only_unified_interaction_response tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_permission_accept_decision_returns_resolved_snapshot_for_command_wait tests/test_inprocess_adapter_frontend_api.py::TestInProcessAdapterFrontendAPI::test_respond_to_interaction_emits_ask_user_tool_finish_and_completes_pending -v
```

Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add src/embedagent/inprocess_adapter.py src/embedagent/core/adapter.py src/embedagent/protocol/__init__.py src/embedagent/frontend/tui tests/test_inprocess_adapter_frontend_api.py tests/test_query_engine_refactor.py
git commit -m "refactor: remove split interaction response APIs"
```

## Task 5: GUI T3 Payloads And Request-Id Response Tracking

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js`
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/src/workbench/workbench-parity-model.js`
- Test: `src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs`
- Test: `src/embedagent/frontend/gui/webapp/test/workbench-parity-model.test.mjs`

- [ ] **Step 1: Update interaction model tests**

In `interaction-model.test.mjs`, change permission response assertions:

```javascript
assert.deepEqual(buildPermissionResponse(permission, "acceptForSession"), {
  decision: "acceptForSession",
});
assert.deepEqual(buildPermissionResponse(permission, "decline"), {
  decision: "decline",
});
```

Change user-input fixture to use `questions`:

```javascript
const ask = normalizeComposerInteraction({
  interaction_id: "ask-1",
  kind: "user_input",
  tool_name: "ask_user",
  questions: [
    {
      id: "answer",
      question: "Continue?",
      options: [
        { index: 1, label: "Continue" },
        { index: 2, label: "Switch to debug", mode: "debug" },
      ],
      multi_select: false,
    },
  ],
});
```

Assert:

```javascript
assert.equal(ask.questions[0].id, "answer");
assert.equal(ask.options[1].label, "Switch to debug");
assert.deepEqual(buildUserInputResponse(ask, { option: ask.options[1] }), {
  answers: { answer: "Switch to debug" },
});
assert.deepEqual(buildUserInputResponse(ask, { answer: "custom path" }), {
  answers: { answer: "custom path" },
});
```

- [ ] **Step 2: Update controller tests for id arrays**

In `interaction-response-controller.test.mjs`, replace single `inFlight` with:

```javascript
let respondingIds = [];
```

Provide callbacks:

```javascript
getRespondingRequestIds: () => respondingIds,
setRespondingRequestIds: (value) => {
  respondingIds = typeof value === "function" ? value(respondingIds) : value;
},
```

Use payload:

```javascript
const first = controller.respondToInteraction({ answers: { answer: "yes" } });
```

Assert `respondingIds.includes("ask-1")` while pending and `respondingIds` is empty after completion.

- [ ] **Step 3: Add waiting_permission interruptibility test**

In `workbench-parity-model.test.mjs`, add:

```javascript
assert.equal(isWorkbenchSessionRunning({ status: "waiting_permission" }), true);
assert.equal(isWorkbenchSessionRunning({ status: "waiting_user_input" }), true);
```

Use the actual exported helper name in that file; if the helper is currently named differently, update the assertion to the existing export.

- [ ] **Step 4: Run frontend tests and confirm red**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- interaction-model interaction-response-controller workbench-parity-model
```

Expected: FAIL because the implementation still emits legacy payloads and tracks one global in-flight id.

- [ ] **Step 5: Update `interaction-model.js`**

Change `normalizeComposerInteraction()` user-input branch to accept `questions` and keep a compatibility read from old `question/options` only inside normalization if tests outside this task still require it. Return:

```javascript
return {
  kind: "user_input",
  interactionId: cleanString(interaction.interaction_id || interaction.request_id),
  summary: "Input requested",
  toolName: cleanString(interaction.tool_name || interaction.toolName),
  questions,
  question: questions[0]?.question || "",
  options: questions[0]?.options || [],
  customPlaceholder: "Or type a custom answer...",
  submitLabel: "Submit",
  rawInteraction: interaction,
};
```

Change payload builders:

```javascript
export function buildPermissionResponse(_interaction, decision) {
  return { decision };
}

export function buildUserInputResponse(_interaction, options = {}) {
  const selected = options.option || null;
  return {
    answers: {
      answer: selected ? selected.label || selected.text || "" : cleanString(options.answer),
    },
  };
}
```

- [ ] **Step 6: Update response controller API**

In `interaction-response-controller.js`, replace `getResponseInFlight`/`setResponseInFlight` with request-id list callbacks while keeping fallback defaults:

```javascript
getRespondingRequestIds,
setRespondingRequestIds,
```

Implement:

```javascript
function isResponding(id) {
  return readRespondingIds().includes(id);
}

function markResponding(id) {
  writeRespondingIds((existing) => (existing.includes(id) ? existing : [...existing, id]));
}

function clearResponding(id) {
  writeRespondingIds((existing) => existing.filter((value) => value !== id));
}
```

Use `markResponding(interactionId)` before fetch and `clearResponding(interactionId)` in `finally`.

- [ ] **Step 7: Update logging**

Change `interactionLogDetail()` to read:

```javascript
if (interaction?.kind === "permission") {
  return String(payload?.decision || "");
}
return String(payload?.answers?.answer || "").slice(0, 40);
```

- [ ] **Step 8: Update `App.jsx` state**

Replace:

```javascript
const [interactionResponseInFlight, setInteractionResponseInFlightState] = useState("");
const interactionResponseInFlightRef = useRef("");
```

with:

```javascript
const [respondingRequestIds, setRespondingRequestIdsState] = useState([]);
const respondingRequestIdsRef = useRef([]);
```

Keep the ref synchronized, and pass the new callbacks into `createInteractionResponseController()`.

Set composer busy with:

```javascript
interactionBusy={Boolean(composerInteraction?.interactionId && respondingRequestIds.includes(composerInteraction.interactionId))}
```

- [ ] **Step 9: Update interruptible status**

Replace status checks that only include `running` and `waiting_user_input` with helper logic:

```javascript
function isTurnInterruptibleStatus(status) {
  return status === "running" || status === "waiting_permission" || status === "waiting_user_input";
}
```

Use it for Escape handling, `isRunning`, and `onStop` visibility.

Update `workbench-parity-model.js` to include `waiting_permission`.

- [ ] **Step 10: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- interaction-model interaction-response-controller workbench-parity-model
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js src/embedagent/frontend/gui/webapp/src/App.jsx src/embedagent/frontend/gui/webapp/src/workbench/workbench-parity-model.js src/embedagent/frontend/gui/webapp/test/interaction-model.test.mjs src/embedagent/frontend/gui/webapp/test/interaction-response-controller.test.mjs src/embedagent/frontend/gui/webapp/test/workbench-parity-model.test.mjs
git commit -m "feat: align GUI interaction responses with T3 semantics"
```

## Task 6: Split Composer Interaction Components

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingApprovalPanel.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingApprovalActions.jsx`
- Create: `src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingUserInputPanel.jsx`
- Modify: `src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs`
- Modify: `src/embedagent/frontend/gui/webapp/test/composer-integration-source.test.mjs`

- [ ] **Step 1: Add source tests for focused modules**

In `composer-components-source.test.mjs`, assert:

```javascript
const approvalPanelSource = readSource("components", "composer", "ComposerPendingApprovalPanel.jsx");
const approvalActionsSource = readSource("components", "composer", "ComposerPendingApprovalActions.jsx");
const userInputPanelSource = readSource("components", "composer", "ComposerPendingUserInputPanel.jsx");

assert.equal(approvalPanelSource.includes("buildPermissionResponse"), false);
assert.equal(approvalActionsSource.includes('"acceptForSession"'), true);
assert.equal(approvalActionsSource.includes('"decline"'), true);
assert.equal(approvalActionsSource.includes('"cancel"'), true);
assert.equal(userInputPanelSource.includes("buildUserInputResponse"), true);
```

- [ ] **Step 2: Run source tests and confirm red**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- composer-components-source composer-integration-source
```

Expected: FAIL because the new files do not exist.

- [ ] **Step 3: Create approval display component**

Create `ComposerPendingApprovalPanel.jsx`:

```javascript
export default function ComposerPendingApprovalPanel({ approval }) {
  if (!approval) return null;
  return (
    <div className="composer-interaction-summary">
      <span className="composer-interaction-eyebrow">Pending approval</span>
      <strong>{approval.summary}</strong>
      {approval.reason ? <span>{approval.reason}</span> : null}
    </div>
  );
}
```

Use existing CSS classes from `ComposerInteractionPanel.jsx`; do not introduce a new visual system.

- [ ] **Step 4: Create approval actions component**

Create `ComposerPendingApprovalActions.jsx`:

```javascript
import { buildPermissionResponse } from "../../session-runtime/interaction-model.js";

export default function ComposerPendingApprovalActions({ approval, busy = false, onRespond }) {
  if (!approval) return null;
  const send = (decision) => {
    if (busy || !onRespond) return;
    onRespond(buildPermissionResponse(approval, decision));
  };
  return (
    <div className="composer-interaction-actions">
      <button type="button" disabled={busy} onClick={() => send("cancel")}>Cancel turn</button>
      <button type="button" disabled={busy} onClick={() => send("decline")}>Decline</button>
      <button type="button" disabled={busy} onClick={() => send("acceptForSession")}>Always allow this session</button>
      <button type="button" disabled={busy} onClick={() => send("accept")}>Approve once</button>
    </div>
  );
}
```

- [ ] **Step 5: Create user-input panel**

Create `ComposerPendingUserInputPanel.jsx`:

```javascript
import { useState } from "react";
import { buildUserInputResponse } from "../../session-runtime/interaction-model.js";

export default function ComposerPendingUserInputPanel({ prompt, busy = false, onRespond }) {
  const [answer, setAnswer] = useState("");
  if (!prompt) return null;
  const submit = (payload) => {
    if (busy || !onRespond) return;
    onRespond(payload);
  };
  return (
    <div className="composer-interaction-user-input">
      <span className="composer-interaction-eyebrow">Input requested</span>
      <strong>{prompt.question}</strong>
      <div className="composer-interaction-options">
        {(prompt.options || []).map((option) => (
          <button
            key={`${option.index || ""}:${option.label || option.text}`}
            type="button"
            disabled={busy}
            onClick={() => submit(buildUserInputResponse(prompt, { option }))}
          >
            {option.shortcut ? <kbd>{option.shortcut}</kbd> : null}
            <span>{option.label || option.text}</span>
          </button>
        ))}
      </div>
      <div className="composer-interaction-custom">
        <input
          value={answer}
          disabled={busy}
          placeholder={prompt.customPlaceholder}
          onChange={(event) => setAnswer(event.target.value)}
        />
        <button
          type="button"
          disabled={busy || !answer.trim()}
          onClick={() => submit(buildUserInputResponse(prompt, { answer }))}
        >
          {prompt.submitLabel || "Submit"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Refactor wrapper**

Update `ComposerInteractionPanel.jsx` to import the three focused components and render:

```javascript
if (view.kind === "permission") {
  return (
    <section className="composer-interaction-panel">
      <ComposerPendingApprovalPanel approval={view} />
      <ComposerPendingApprovalActions approval={view} busy={busy} onRespond={onRespond} />
    </section>
  );
}
if (view.kind === "user_input") {
  return (
    <section className="composer-interaction-panel">
      <ComposerPendingUserInputPanel prompt={view} busy={busy} onRespond={onRespond} />
    </section>
  );
}
```

Keep notice rendering in the wrapper or move it to a small local helper in the same file.

- [ ] **Step 7: Run frontend tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test -- composer-components-source composer-integration-source interaction-model
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/embedagent/frontend/gui/webapp/src/components/composer src/embedagent/frontend/gui/webapp/test/composer-components-source.test.mjs src/embedagent/frontend/gui/webapp/test/composer-integration-source.test.mjs
git commit -m "refactor: split composer pending interaction panels"
```

## Task 7: Backend Route And HTTP Error Contract

**Files:**
- Modify: `tests/test_gui_backend_api.py`
- Modify: `src/embedagent/frontend/gui/backend/http_errors.py`
- Modify: `src/embedagent/frontend/gui/backend/protocol_payloads.py`
- Modify: `src/embedagent/frontend/gui/backend/routes_sessions.py`

- [ ] **Step 1: Update GUI backend route tests**

In `tests/test_gui_backend_api.py`, update interaction route tests to send:

```python
{"decision": "accept"}
```

for permissions and:

```python
{"answers": {"answer": "继续"}}
```

for user input.

Assert the fake core receives the exact payload without backend-side mutation.

- [ ] **Step 2: Add error mapping tests**

Add route tests where fake core raises:

```python
ValueError("interaction_expired")
ValueError("interaction_conflict")
ValueError("invalid_interaction_response")
```

Assert route endpoint raises HTTP status 410, 409, and 422 respectively.

- [ ] **Step 3: Run route tests and confirm red if mappings are missing**

Run:

```bash
uv run pytest tests/test_gui_backend_api.py -k "interaction_response" -v
```

Expected: FAIL if tests still expect legacy payloads or if error mappings are incomplete.

- [ ] **Step 4: Update serializer if needed**

In `protocol_payloads.py`, ensure `serialize_interaction_response()` returns:

```python
{
    "session_id": ...,
    "interaction_id": ...,
    "status": ...,
    "snapshot": serialize_session_snapshot(...),
}
```

Do not add permission remember side effects in GUI backend.

- [ ] **Step 5: Update HTTP error mapping**

In `http_errors.py`, map:

```python
if "interaction_expired" in message:
    return HTTPException(status_code=410, detail="interaction_expired")
if "interaction_conflict" in message:
    return HTTPException(status_code=409, detail="interaction_conflict")
if "invalid_interaction_response" in message:
    return HTTPException(status_code=422, detail="invalid_interaction_response")
```

- [ ] **Step 6: Run route tests**

Run:

```bash
uv run pytest tests/test_gui_backend_api.py -k "interaction_response" -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/test_gui_backend_api.py src/embedagent/frontend/gui/backend/http_errors.py src/embedagent/frontend/gui/backend/protocol_payloads.py src/embedagent/frontend/gui/backend/routes_sessions.py
git commit -m "test: enforce unified GUI interaction route payloads"
```

## Task 8: Final Architecture Cleanup And Static Build

**Files:**
- Modify: `src/embedagent/frontend/gui/static/` generated files only through `npm run build`
- Review: all changed files

- [ ] **Step 1: Search for forbidden old contracts**

Run:

```bash
rg -n "approve_permission|reject_permission|reply_user_input|pending_permission|pending_user_input|pending_result|pending_user_event|pending_user_response|response_kind|selected_mode|selected_option_text|remember:" src tests
```

Expected: No active-source occurrences of old public response methods, split hosted runtime state fields, or legacy shell response payload fields. `record_pending_permission`, `record_pending_user_input`, `selected_mode` inside Core `UserInputResponse` handling, and guard strings in `tests/test_pre_release_architecture_guards.py` are allowed because they are durable Core/internal diagnostics, not shell response contracts.

- [ ] **Step 2: Run architecture gates**

Run:

```bash
uv run pytest tests/test_pre_release_architecture_guards.py tests/test_current_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 3: Run focused interaction tests**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py tests/test_gui_backend_api.py -k "interaction or permission or user_input" -v
```

Expected: PASS.

- [ ] **Step 4: Run fast Python suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: PASS.

- [ ] **Step 5: Run lint**

Run:

```bash
uv run --locked python scripts/lint.py
```

Expected: PASS.

- [ ] **Step 6: Run webapp tests**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm test
```

Expected: PASS.

- [ ] **Step 7: Build webapp static assets**

Run:

```bash
cd src/embedagent/frontend/gui/webapp
npm run build
```

Expected: PASS and generated assets under `src/embedagent/frontend/gui/static/` updated if webapp source changed.

- [ ] **Step 8: Review diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: Only intentional source, tests, docs, and generated GUI static assets are changed. `config/config.json` and `uv.lock` are not changed.

- [ ] **Step 9: Commit final cleanup/build**

```bash
git add src tests docs/superpowers/plans/2026-06-30-interaction-lifecycle-convergence.md
git commit -m "chore: verify interaction lifecycle convergence"
```

## Self-Review Checklist

- Spec coverage: Tasks cover Core truth preservation, single hosted ticket, T3 `decision`/`answers` payloads, Pi-style cancel/abort ownership, GUI read-model/request-id tracking, TUI unified response, public API deletion, architecture guards, and final verification gates.
- Scope boundaries: The plan does not add T3 projection persistence, multi-pending runtime support, full multi-question Core `ask_user`, new dependencies, or PermissionPolicy rule semantic changes.
- Python compatibility: All Python snippets use Python 3.8-compatible syntax.
- Verification: Each task has a red test or guard, a focused implementation step, a targeted verification command, and a commit point.
