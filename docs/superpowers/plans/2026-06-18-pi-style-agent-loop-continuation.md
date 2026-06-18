# Pi-Style Agent Loop Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the product-facing default `max_turns=8` ceiling with a Pi-style open continuation loop while preserving explicit safety-limit compatibility.

**Architecture:** Add a tiny internal continuation-policy module next to `AgentLoop`, then convert `AgentLoop.run()` from `for range(max_turns)` to an open `while True` loop that asks the policy at step boundaries. `max_turns` remains accepted as a legacy configuration name, but an omitted value means no default turn-count cutoff; explicit positive values still stop with the compatibility `max_turns` transition.

**Tech Stack:** Python 3.8 stdlib dataclasses/typing, existing `AgentLoop` / `QueryEngine` / `InProcessAdapter`, existing transcript/session projections, existing pytest suite, existing docs.

---

## File Structure

- Create `src/embedagent/agent_loop_continuation.py`
  - Internal decision and facts dataclasses.
  - Default policy for completion, stop-event aborts, explicit safety-limit stops, and normal continuation.
  - No workflow imports, provider imports, frontend imports, network calls, or new dependencies.
- Create `tests/test_agent_loop_continuation.py`
  - Unit tests for default continuation decisions and compatibility metadata.
- Modify `src/embedagent/agent_loop.py`
  - Accept `Optional[int]` `max_turns`.
  - Keep `self.max_turns` as the compatibility attribute.
  - Add `self.loop_safety_limit` as the clearer internal name.
  - Replace `for turn_index in range(self.max_turns)` with an open loop.
  - Preserve existing completion, compact retry, guard-stop, abort, pending-interaction, lifecycle, and tool execution paths.
- Modify `src/embedagent/query_engine.py`
  - Change default `max_turns` from `8` to `None`.
  - Pass the value through to `AgentLoop` without taking loop ownership back from `AgentLoop`.
- Modify `src/embedagent/inprocess_adapter.py`
  - Change default `max_turns` from `8` to `None`.
  - Continue projecting `max_turns` in snapshots/events for compatibility; omitted safety limit projects as `None`.
- Modify runtime entrypoints that currently synthesize `8`
  - `src/embedagent/core/adapter.py`
  - `src/embedagent/frontend/tui/launcher.py`
  - `src/embedagent/frontend/tui/bootstrap.py`
  - `src/embedagent/frontend/gui/launcher.py`
  - CLI help text in `src/embedagent/cli.py`
- Modify frontend source default display handling
  - `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
  - `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`
- Modify tests
  - `tests/test_query_engine_refactor.py`
  - Keep existing explicit `max_turns=1` adapter/history tests green.
- Modify docs after implementation
  - `README.md`
  - `AGENTS.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/development-tracker.md`
  - `docs/design-change-log.md`
  - `docs/guides/configuration-guide.md`
  - `docs/frontend-protocol.md`
  - `docs/modules/agent-core.md`
  - `docs/pi-inspired-agent-core-blueprint.md`
  - `src/embedagent/config.py` module docstring
  - `src/embedagent/session.py` transition docstring

## Constraints For Every Task

- Keep runtime Python syntax compatible with `>=3.8,<3.9`.
- Do not add dependencies.
- Do not introduce Docker, WSL, VS Code, runtime Node, online services, or network-required behavior.
- Do not move C/C++ workflow policy into Agent Core.
- Do not move context compaction ownership out of `ContextManager`.
- Do not weaken `LoopGuard`, `PermissionPolicy`, pending interaction, or stop-event behavior.
- Do not rename the public `max_turns` constructor/config field in this slice.
- Do not add a public extension API for continuation policy in this slice.
- Preserve `LoopTransition.reason == "max_turns"` for explicit safety-limit stops so existing projections remain compatible.

## Task 1: Add The Continuation Policy Unit

**Files:**
- Create: `src/embedagent/agent_loop_continuation.py`
- Create: `tests/test_agent_loop_continuation.py`

- [ ] **Step 1: Write the failing policy tests**

Create `tests/test_agent_loop_continuation.py` with this content:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.agent_loop_continuation import (
    CONTINUATION_ABORT,
    CONTINUATION_CONTINUE,
    CONTINUATION_STOP,
    AgentLoopContinuationFacts,
    DefaultAgentLoopContinuationPolicy,
)


class TestAgentLoopContinuationPolicy(unittest.TestCase):
    def test_completion_signal_stops_normally(self):
        policy = DefaultAgentLoopContinuationPolicy()

        decision = policy.decide_after_step(
            AgentLoopContinuationFacts(
                step_index=1,
                turns_used=1,
                mode_name="build",
                workflow_state="chat",
                completion_signal=True,
            )
        )

        self.assertEqual(decision.kind, CONTINUATION_STOP)
        self.assertEqual(decision.reason, "completed")
        self.assertEqual(decision.message, "agent signaled completion")
        self.assertEqual(decision.next_mode, "build")

    def test_tool_step_continues_before_safety_limit(self):
        policy = DefaultAgentLoopContinuationPolicy()

        decision = policy.decide_after_step(
            AgentLoopContinuationFacts(
                step_index=3,
                turns_used=3,
                mode_name="build",
                workflow_state="chat",
                has_tool_calls=True,
                safety_limit=8,
                safety_limit_reached=False,
            )
        )

        self.assertEqual(decision.kind, CONTINUATION_CONTINUE)
        self.assertEqual(decision.reason, "")

    def test_explicit_safety_limit_uses_max_turns_compatibility_reason(self):
        policy = DefaultAgentLoopContinuationPolicy()

        decision = policy.decide_after_step(
            AgentLoopContinuationFacts(
                step_index=1,
                turns_used=1,
                mode_name="build",
                workflow_state="chat",
                safety_limit=1,
                safety_limit_reached=True,
            )
        )

        self.assertEqual(decision.kind, CONTINUATION_STOP)
        self.assertEqual(decision.reason, "max_turns")
        self.assertEqual(
            decision.message,
            "reached loop safety limit without completion signal",
        )
        self.assertEqual(decision.metadata["loop_safety_limit"], 1)
        self.assertEqual(decision.metadata["turns_used"], 1)

    def test_stop_event_aborts(self):
        policy = DefaultAgentLoopContinuationPolicy()

        decision = policy.decide_after_step(
            AgentLoopContinuationFacts(
                step_index=0,
                turns_used=0,
                mode_name="build",
                workflow_state="chat",
                stop_event_set=True,
            )
        )

        self.assertEqual(decision.kind, CONTINUATION_ABORT)
        self.assertEqual(decision.reason, "aborted")
        self.assertEqual(decision.message, "stop_event set")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the policy tests and confirm the module is missing**

Run:

```bash
uv run pytest tests/test_agent_loop_continuation.py -v
```

Expected: failure with `ModuleNotFoundError: No module named 'embedagent.agent_loop_continuation'`.

- [ ] **Step 3: Add the continuation policy module**

Create `src/embedagent/agent_loop_continuation.py` with this content:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

CONTINUATION_CONTINUE = "continue"
CONTINUATION_STOP = "stop"
CONTINUATION_ABORT = "abort"
CONTINUATION_WAIT = "wait"
CONTINUATION_COMPACT_THEN_CONTINUE = "compact_then_continue"


@dataclass
class AgentLoopContinuationFacts:
    step_index: int = 0
    turns_used: int = 0
    mode_name: str = ""
    workflow_state: str = ""
    has_tool_calls: bool = False
    completion_signal: bool = False
    stop_event_set: bool = False
    safety_limit: Optional[int] = None
    safety_limit_reached: bool = False
    compacted: bool = False
    pending_interaction_reason: str = ""
    guard_stop_reason: str = ""


@dataclass
class AgentLoopContinuationDecision:
    kind: str
    reason: str = ""
    message: str = ""
    next_mode: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentLoopContinuationPolicy(object):
    def decide_after_step(
        self, facts: AgentLoopContinuationFacts
    ) -> AgentLoopContinuationDecision:
        raise NotImplementedError


class DefaultAgentLoopContinuationPolicy(AgentLoopContinuationPolicy):
    def decide_after_step(
        self, facts: AgentLoopContinuationFacts
    ) -> AgentLoopContinuationDecision:
        if facts.stop_event_set:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_ABORT,
                reason="aborted",
                message="stop_event set",
            )
        if facts.pending_interaction_reason:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_WAIT,
                reason=facts.pending_interaction_reason,
            )
        if facts.guard_stop_reason:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_STOP,
                reason="guard_stop",
                message=facts.guard_stop_reason,
            )
        if facts.completion_signal:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_STOP,
                reason="completed",
                message="agent signaled completion",
                next_mode=facts.mode_name,
            )
        if facts.safety_limit_reached:
            return AgentLoopContinuationDecision(
                kind=CONTINUATION_STOP,
                reason="max_turns",
                message="reached loop safety limit without completion signal",
                metadata={
                    "loop_safety_limit": facts.safety_limit,
                    "turns_used": facts.turns_used,
                    "compatibility_reason": "max_turns",
                },
            )
        return AgentLoopContinuationDecision(kind=CONTINUATION_CONTINUE)
```

- [ ] **Step 4: Run the policy tests and confirm they pass**

Run:

```bash
uv run pytest tests/test_agent_loop_continuation.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit the policy unit**

Run:

```bash
git add src/embedagent/agent_loop_continuation.py tests/test_agent_loop_continuation.py
git commit -m "feat: add agent loop continuation policy"
```

Expected: commit succeeds.

## Task 2: Convert AgentLoop To Open Continuation

**Files:**
- Modify: `src/embedagent/agent_loop.py`
- Test: `tests/test_query_engine_refactor.py`
- Test: `tests/test_inprocess_adapter_frontend_api.py`

- [ ] **Step 1: Add imports and constructor fields**

In `src/embedagent/agent_loop.py`, extend the imports:

```python
from typing import Any, Callable, Optional

from embedagent.agent_loop_continuation import (
    CONTINUATION_ABORT,
    CONTINUATION_COMPACT_THEN_CONTINUE,
    CONTINUATION_CONTINUE,
    CONTINUATION_STOP,
    AgentLoopContinuationDecision,
    AgentLoopContinuationFacts,
    AgentLoopContinuationPolicy,
    DefaultAgentLoopContinuationPolicy,
)
```

Change the constructor signature from:

```python
        max_turns: int = 8,
```

to:

```python
        max_turns: Optional[int] = None,
```

Add this optional dependency near the other constructor parameters:

```python
        continuation_policy: Optional[AgentLoopContinuationPolicy] = None,
```

Replace the existing assignment:

```python
        self.max_turns = max_turns
```

with:

```python
        self.loop_safety_limit = self._normalize_safety_limit(max_turns)
        self.max_turns = self.loop_safety_limit
        self.continuation_policy = continuation_policy or DefaultAgentLoopContinuationPolicy()
```

- [ ] **Step 2: Add small loop helpers**

Inside `AgentLoop`, above `_ensure_configured`, add these methods:

```python
    @staticmethod
    def _normalize_safety_limit(value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        limit = int(value)
        if limit <= 0:
            return None
        return limit

    def _safety_limit_reached(self, completed_steps: int) -> bool:
        return (
            self.loop_safety_limit is not None
            and int(completed_steps or 0) >= self.loop_safety_limit
        )

    def _transition_from_decision(
        self,
        decision: AgentLoopContinuationDecision,
        fallback_reason: str,
        fallback_message: str,
        turns_used: int,
        fallback_next_mode: str = "",
    ) -> LoopTransition:
        return LoopTransition(
            reason=decision.reason or fallback_reason,
            message=decision.message or fallback_message,
            next_mode=decision.next_mode or fallback_next_mode,
            turns_used=turns_used,
            metadata=dict(decision.metadata or {}),
        )
```

- [ ] **Step 3: Replace the fixed for-loop head**

In `AgentLoop.run()`, replace:

```python
        for turn_index in range(self.max_turns):
            if stop_event is not None and stop_event.is_set():
                transition = LoopTransition(
                    reason="aborted", message="stop_event set", turns_used=turns_used
                )
                self._record_transition(session, transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            step_index = turn_index + 1
```

with:

```python
        turn_index = 0
        force_compact_next_step = False
        while True:
            if stop_event is not None and stop_event.is_set():
                decision = self.continuation_policy.decide_after_step(
                    AgentLoopContinuationFacts(
                        step_index=turn_index,
                        turns_used=turns_used,
                        mode_name=current_mode,
                        workflow_state=workflow_state,
                        stop_event_set=True,
                    )
                )
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason="aborted",
                    fallback_message="stop_event set",
                    turns_used=turns_used,
                )
                self._record_transition(session, transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            if self._safety_limit_reached(turn_index):
                decision = self.continuation_policy.decide_after_step(
                    AgentLoopContinuationFacts(
                        step_index=turn_index,
                        turns_used=turns_used,
                        mode_name=current_mode,
                        workflow_state=workflow_state,
                        safety_limit=self.loop_safety_limit,
                        safety_limit_reached=True,
                    )
                )
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason="max_turns",
                    fallback_message="reached loop safety limit without completion signal",
                    turns_used=turns_used,
                )
                self._record_transition(session, transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            turn_index += 1
            step_index = turn_index
```

- [ ] **Step 4: Carry policy-requested compaction into the next step**

In the same method, replace:

```python
            force_compact = False
```

with:

```python
            force_compact = force_compact_next_step
            force_compact_next_step = False
```

This keeps compaction execution inside the existing context pipeline; the policy only asks for the next context assembly to use the existing forced-compaction path.

- [ ] **Step 5: Route completion through the policy**

Replace the current completion block:

```python
            if self._is_completion_signal(reply, session):
                transition = LoopTransition(
                    reason="completed",
                    message="agent signaled completion",
                    next_mode=current_mode,
                    turns_used=turns_used,
                )
                self._record_transition(session, transition)
                self._persist_summary(session, current_mode, assembly)
                if not compact_boundary_recorded:
                    self._maybe_record_compact_boundary(session, current_mode, assembly)
                self._maybe_maintain_memory(True)
                if on_step_finish is not None:
                    on_step_finish(step_index, reply, "completed")
                return QueryTurnResult(final_text, session, transition, turns_used)
```

with:

```python
            if self._is_completion_signal(reply, session):
                decision = self.continuation_policy.decide_after_step(
                    AgentLoopContinuationFacts(
                        step_index=step_index,
                        turns_used=turns_used,
                        mode_name=current_mode,
                        workflow_state=workflow_state,
                        has_tool_calls=bool(reply.actions),
                        completion_signal=True,
                        compacted=bool(compact_boundary_recorded),
                    )
                )
                if decision.kind == CONTINUATION_CONTINUE:
                    continue
                if decision.kind == CONTINUATION_COMPACT_THEN_CONTINUE:
                    force_compact_next_step = True
                    continue
                if decision.kind not in (CONTINUATION_STOP, CONTINUATION_ABORT):
                    raise RuntimeError("Unsupported continuation decision: %s" % decision.kind)
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason="completed",
                    fallback_message="agent signaled completion",
                    turns_used=turns_used,
                    fallback_next_mode=current_mode,
                )
                self._record_transition(session, transition)
                self._persist_summary(session, current_mode, assembly)
                if not compact_boundary_recorded:
                    self._maybe_record_compact_boundary(session, current_mode, assembly)
                self._maybe_maintain_memory(True)
                if on_step_finish is not None:
                    on_step_finish(step_index, reply, transition.reason)
                return QueryTurnResult(final_text, session, transition, turns_used)
```

- [ ] **Step 6: Ask the policy after tool steps**

At the end of the tool-call path, after `_emit_step_finished(...)`, add:

```python
            decision = self.continuation_policy.decide_after_step(
                AgentLoopContinuationFacts(
                    step_index=step_index,
                    turns_used=turns_used,
                    mode_name=current_mode,
                    workflow_state=workflow_state,
                    has_tool_calls=bool(reply.actions),
                    completion_signal=False,
                    compacted=bool(compact_boundary_recorded),
                )
            )
            if decision.kind == CONTINUATION_CONTINUE:
                continue
            if decision.kind == CONTINUATION_COMPACT_THEN_CONTINUE:
                force_compact_next_step = True
                continue
            if decision.kind in (CONTINUATION_STOP, CONTINUATION_ABORT):
                transition = self._transition_from_decision(
                    decision,
                    fallback_reason=decision.reason or "aborted",
                    fallback_message=decision.message or "",
                    turns_used=turns_used,
                )
                self._record_transition(session, transition)
                return QueryTurnResult(final_text, session, transition, turns_used)
            raise RuntimeError("Unsupported continuation decision: %s" % decision.kind)
```

- [ ] **Step 7: Remove the old post-loop terminal block**

Delete the old code after the `for` loop:

```python
        transition = LoopTransition(
            reason="max_turns",
            message="reached max turns without completion signal",
            turns_used=turns_used,
        )
        self._record_transition(session, transition)
        return QueryTurnResult(final_text, session, transition, turns_used)
```

The safety-limit transition is now produced at the top of the open loop before a new step begins.

- [ ] **Step 8: Run focused existing loop tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_projection_failure_does_not_flip_tool_success tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_query_engine_exposes_slim_agent_components -v
```

Expected: both tests pass.

- [ ] **Step 9: Run existing adapter max-turn compatibility tests**

Run:

```bash
uv run pytest tests/test_inprocess_adapter_frontend_api.py -k max_turns -v
```

Expected: existing explicit `max_turns=1` tests pass and still report transition reason `max_turns`.

- [ ] **Step 10: Commit the open-loop conversion**

Run:

```bash
git add src/embedagent/agent_loop.py
git commit -m "feat: use open continuation loop in agent core"
```

Expected: commit succeeds.

## Task 3: Remove The Default Eight-Turn Product Ceiling

**Files:**
- Modify: `src/embedagent/query_engine.py`
- Modify: `src/embedagent/inprocess_adapter.py`
- Modify: `src/embedagent/core/adapter.py`
- Modify: `src/embedagent/frontend/tui/launcher.py`
- Modify: `src/embedagent/frontend/tui/bootstrap.py`
- Modify: `src/embedagent/frontend/gui/launcher.py`
- Modify: `src/embedagent/cli.py`
- Test: `tests/test_query_engine_refactor.py`
- Test: `tests/test_gui_runtime.py`
- Test: `tests/test_query_engine_orchestrator.py`

- [ ] **Step 1: Change QueryEngine and InProcessAdapter defaults**

In `src/embedagent/query_engine.py`, change:

```python
        max_turns: int = 8,
```

to:

```python
        max_turns: Optional[int] = None,
```

In `src/embedagent/inprocess_adapter.py`, change:

```python
        max_turns: int = 8,
```

to:

```python
        max_turns: Optional[int] = None,
```

Keep these assignments unchanged:

```python
        self.max_turns = max_turns
```

They preserve the existing compatibility attribute and snapshot field.

- [ ] **Step 2: Stop adapter initialization from synthesizing 8**

In `src/embedagent/core/adapter.py`, replace:

```python
            "max_turns": kwargs.get("max_turns", 8),
```

with:

```python
            "max_turns": kwargs.get("max_turns"),
```

- [ ] **Step 3: Stop TUI launcher from synthesizing 8**

In `src/embedagent/frontend/tui/launcher.py`, replace:

```python
    resolved_max_turns = int(_resolve_runtime_value(max_turns, app_config.max_turns, 8))
```

with:

```python
    raw_max_turns = _resolve_runtime_value(max_turns, app_config.max_turns, None)
    resolved_max_turns = int(raw_max_turns) if raw_max_turns is not None else None
```

In `src/embedagent/frontend/tui/bootstrap.py`, add:

```python
from typing import Optional
```

and change:

```python
    max_turns: int,
```

to:

```python
    max_turns: Optional[int],
```

- [ ] **Step 4: Stop GUI launcher from synthesizing 8**

In `src/embedagent/frontend/gui/launcher.py`, replace:

```python
    max_turns = int(_resolve_runtime_value(options.get("max_turns"), app_config.max_turns, 8))
```

with:

```python
    raw_max_turns = _resolve_runtime_value(options.get("max_turns"), app_config.max_turns, None)
    max_turns = int(raw_max_turns) if raw_max_turns is not None else None
```

- [ ] **Step 5: Update CLI help text without changing the flag name**

In `src/embedagent/cli.py`, find the `--max-turns` argument and change the help text to:

```python
help="Optional model/tool loop safety limit; omit for open continuation"
```

In `src/embedagent/frontend/tui/launcher.py` and `src/embedagent/frontend/gui/launcher.py`, make the same help-text change for their `--max-turns` arguments.

- [ ] **Step 6: Add a long-continuation regression client**

In `tests/test_query_engine_refactor.py`, add this client near `ToolClient`:

```python
class LongToolThenDoneClient(object):
    def __init__(self, tool_turns):
        self.calls = 0
        self.tool_turns = int(tool_turns)

    def generate(self, messages, tools=None):
        self.calls += 1
        if self.calls <= self.tool_turns:
            return AssistantReply(
                content="",
                actions=[
                    Action(
                        name="read_file",
                        arguments={"path": "src/step_%02d.c" % self.calls},
                        call_id="read-step-%02d" % self.calls,
                    )
                ],
                finish_reason="tool_calls",
            )
        return AssistantReply(
            content="done after %s tool turns" % self.tool_turns,
            actions=[],
            finish_reason="stop",
        )

    def stream(self, messages, tools=None, on_text_delta=None, on_reasoning_delta=None):
        reply = self.generate(messages, tools=tools)
        if on_text_delta is not None and reply.content:
            on_text_delta(reply.content)
        return reply
```

- [ ] **Step 7: Add distinct files for the long-continuation test**

In `TestQueryEngineRefactor.setUp`, after creating `src/demo.c`, add:

```python
        for index in range(1, 11):
            with open(
                os.path.join(self.workspace, "src", "step_%02d.c" % index),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write("int step_%02d(void) {\n    return %d;\n}\n" % (index, index))
```

Distinct files keep the test inside existing `LoopGuard` semantics instead of hiding repeated-tool protection.

- [ ] **Step 8: Add the default continuation regression**

In `TestQueryEngineRefactor`, add:

```python
    def test_default_agent_loop_continues_past_eight_tool_steps(self):
        client = LongToolThenDoneClient(tool_turns=9)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="读取多个文件后完成",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "completed")
        self.assertEqual(result.turns_used, 10)
        self.assertEqual(client.calls, 10)
        self.assertGreater(result.turns_used, 8)
```

- [ ] **Step 9: Add the explicit safety-limit regression**

In `TestQueryEngineRefactor`, add:

```python
    def test_explicit_loop_safety_limit_still_stops_after_configured_step_count(self):
        client = LongToolThenDoneClient(tool_turns=2)
        engine = QueryEngine(
            client=client,
            tools=self.tools,
            max_turns=1,
            permission_policy=PermissionPolicy(
                auto_approve_all=True,
                workspace=self.workspace,
            ),
        )
        session = Session()
        session.add_system_message("你是 EmbedAgent 的受控模式原型。\n当前模式：build")

        result = engine.submit_user_turn(
            user_text="读取多个文件但安全限制为一步",
            stream=False,
            initial_mode="build",
            session=session,
        )

        self.assertEqual(result.transition.reason, "max_turns")
        self.assertEqual(result.turns_used, 1)
        self.assertEqual(result.transition.metadata.get("loop_safety_limit"), 1)
        self.assertEqual(result.transition.metadata.get("turns_used"), 1)
        self.assertEqual(client.calls, 1)
```

- [ ] **Step 10: Run the new loop regression tests**

Run:

```bash
uv run pytest tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_default_agent_loop_continues_past_eight_tool_steps tests/test_query_engine_refactor.py::TestQueryEngineRefactor::test_explicit_loop_safety_limit_still_stops_after_configured_step_count -v
```

Expected: both tests pass.

- [ ] **Step 11: Run constructor and GUI runtime tests**

Run:

```bash
uv run pytest tests/test_query_engine_orchestrator.py tests/test_gui_runtime.py -v
```

Expected: tests pass. Explicit `max_turns=8` and `max_turns=11` assertions continue to pass because explicit values are still honored.

- [ ] **Step 12: Commit default-ceiling removal**

Run:

```bash
git add src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py src/embedagent/core/adapter.py src/embedagent/frontend/tui/launcher.py src/embedagent/frontend/tui/bootstrap.py src/embedagent/frontend/gui/launcher.py src/embedagent/cli.py tests/test_query_engine_refactor.py
git commit -m "feat: remove default eight turn ceiling"
```

Expected: commit succeeds.

## Task 4: Update Frontend Compatibility Projection

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`
- Modify: `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`

- [ ] **Step 1: Change missing maxTurns fallback to null**

In `src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js`, replace both occurrences of:

```js
        maxTurns: payload.payload?.max_turns || 8,
```

and:

```js
      maxTurns: payload?.max_turns || 8,
```

with:

```js
        maxTurns: payload.payload?.max_turns ?? null,
```

and:

```js
      maxTurns: payload?.max_turns ?? null,
```

- [ ] **Step 2: Add a no-safety-limit frontend test**

In `src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs`, add this test near the existing `turn_end` / transition tests:

```js
export function testTurnEndWithoutSafetyLimitProjectsNullMaxTurns() {
  const effects = derive("turn_end", {
    termination_reason: "completed",
    display_reason: "completed",
    message: "Done.",
    turns_used: 10,
  });

  const action = effects.actions.find((item) => item.type === "turn_ended");
  assert.equal(action.maxTurns, null);
  assert.equal(action.turnsUsed, 10);
  assert.equal(action.terminationReason, "completed");
}
```

If the test file exports an explicit runner list, add `testTurnEndWithoutSafetyLimitProjectsNullMaxTurns` to that list.

- [ ] **Step 3: Run frontend unit tests**

Run:

```bash
node src/embedagent/frontend/gui/webapp/test/run-tests.mjs
```

Expected: all webapp tests pass.

- [ ] **Step 4: Commit frontend projection update**

Run:

```bash
git add src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js src/embedagent/frontend/gui/webapp/test/socket-message-effects.test.mjs
git commit -m "fix: project missing loop safety limit as null"
```

Expected: commit succeeds.

## Task 5: Update Documentation And Inline Contracts

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/overall-solution-architecture.md`
- Modify: `docs/implementation-roadmap.md`
- Modify: `docs/development-tracker.md`
- Modify: `docs/design-change-log.md`
- Modify: `docs/guides/configuration-guide.md`
- Modify: `docs/frontend-protocol.md`
- Modify: `docs/modules/agent-core.md`
- Modify: `docs/pi-inspired-agent-core-blueprint.md`
- Modify: `src/embedagent/config.py`
- Modify: `src/embedagent/session.py`

- [ ] **Step 1: Update `README.md` core summary**

In `README.md`, replace the `AgentLoop` bullet:

```markdown
- `src/embedagent/agent_loop.py`
  Turn-loop owner for agent steps, provider/context attempts, compact retry, tool batches, guard stops, abort transitions, and max-turn termination.
```

with:

```markdown
- `src/embedagent/agent_loop.py`
  Pi-style open continuation loop for agent steps, provider/context attempts, compact retry, tool batches, guard stops, abort transitions, and explicit loop safety-limit compatibility transitions.
- `src/embedagent/agent_loop_continuation.py`
  Internal continuation decision policy for open-loop stop, continue, abort, and safety-limit behavior.
```

Also replace the top-level ownership bullet text:

```markdown
turn-loop orchestration, non-LLM tool action execution, and extension hook dispatch
```

with:

```markdown
open turn-loop continuation, non-LLM tool action execution, and extension hook dispatch
```

- [ ] **Step 2: Update `AGENTS.md` architecture vocabulary**

In `AGENTS.md`, replace:

```markdown
`AgentLifecycleJournal`, `AgentKernel`, `AgentLoop`, `TurnSnapshot`, `CapabilityRegistry`, `RuntimeConfigReducer`, `WorkflowPackageManifest`, `CompactionStateReducer`, and `RecoveryStateReducer` are implemented internal Agent Core boundaries/read models, not public extension APIs.
```

with:

```markdown
`AgentLifecycleJournal`, `AgentKernel`, `AgentLoop`, `AgentLoopContinuationPolicy`, `TurnSnapshot`, `CapabilityRegistry`, `RuntimeConfigReducer`, `WorkflowPackageManifest`, `CompactionStateReducer`, and `RecoveryStateReducer` are implemented internal Agent Core boundaries/read models, not public extension APIs.
```

Replace the `AgentLoop` ownership sentence:

```markdown
`AgentLoop` owns turn-loop orchestration behind the session facade, including agent steps, provider/context attempts, compact retry, guard-stop, abort, and max-turn transitions.
```

with:

```markdown
`AgentLoop` owns Pi-style open turn-loop continuation behind the session facade, including agent steps, provider/context attempts, compact retry, guard-stop, abort, and explicit loop safety-limit compatibility transitions. `max_turns` remains accepted as the legacy configuration field for that optional safety fuse; omitted values must not recreate a default eight-turn product ceiling.
```

- [ ] **Step 3: Update architecture docs**

In `docs/overall-solution-architecture.md`, `docs/implementation-roadmap.md`, `docs/modules/agent-core.md`, and `docs/pi-inspired-agent-core-blueprint.md`, replace descriptions of `AgentLoop` owning `max-turn transitions` with this wording:

```markdown
`AgentLoop` owns Pi-style open turn-loop continuation: agent step lifecycle, context/provider attempts, compact retry, tool batch interruption, guard-stop, abort, and explicit loop safety-limit compatibility transitions. The optional safety fuse is still configured through the legacy `max_turns` field, but the hosted default no longer stops merely because eight model/tool cycles were used.
```

- [ ] **Step 4: Update configuration guide and config docstring**

In `docs/guides/configuration-guide.md`, change the JSON example from:

```json
  "max_turns": 8,
```

to:

```json
  "max_turns": null,
```

Change the loop defaults table row from:

```markdown
| `max_turns` | integer | `8` | Maximum model/tool loop turns for one request |
```

to:

```markdown
| `max_turns` | integer or null | `null` | Optional model/tool loop safety limit; omit or set null for Pi-style open continuation |
```

In `src/embedagent/config.py`, make the same example change in the module docstring.

- [ ] **Step 5: Update frontend protocol wording**

In `docs/frontend-protocol.md`, add this paragraph under the session snapshot field list:

```markdown
`max_turns`, where present in snapshots or turn-end events, is a compatibility projection for the optional loop safety limit. A missing or null value means the default Pi-style continuation path has no fixed turn-count cutoff. Frontends may display the value for diagnostics, but they must not treat it as a required session budget or infer loop policy from it.
```

- [ ] **Step 6: Update session transition docstring**

In `src/embedagent/session.py`, replace:

```python
    ``"max_turns"``   — hit the ``max_turns`` ceiling.
```

with:

```python
    ``"max_turns"``   — hit the explicit loop safety limit configured through
    the legacy ``max_turns`` field.
```

Keep the `termination_reason` compatibility value unchanged.

- [ ] **Step 7: Add tracker and changelog entries**

In `docs/development-tracker.md`, add a current status bullet near the other Agent Core ownership bullets:

```markdown
- 最新 Pi-style continuation slice：`AgentLoop` 已从固定 `max_turns=8` product ceiling 改为开放 continuation loop；默认 hosted 路径不再按 8 个 model/tool cycles 截断，显式 `max_turns` 仍作为 loop safety fuse 并继续投影兼容 `max_turns` transition。
```

In `docs/design-change-log.md`, add a dated entry:

```markdown
## 2026-06-18 - Pi-style agent loop continuation

- `AgentLoop` now runs as an open continuation loop instead of a fixed `for range(max_turns)` loop.
- The default hosted path no longer synthesizes `max_turns=8`; omitted `max_turns` means no fixed turn-count cutoff.
- Explicit positive `max_turns` values remain supported as a loop safety fuse and continue to emit compatibility `max_turns` transitions with `loop_safety_limit` metadata.
- `AgentLoopContinuationPolicy` is an internal Agent Core boundary, not a public extension API.
```

- [ ] **Step 8: Run docs spelling/search checks for stale default wording**

Run:

```bash
rg -n "max_turns` \\| integer \\| `8`|max_turns=8|default.*8|for range\\(max_turns\\)|Maximum model/tool loop turns" README.md AGENTS.md docs src tests
```

Expected: no stale documentation claims that the default loop limit is 8. Explicit test fixtures with `max_turns=8`, historical archive references, and GUI fixture payloads with explicit `max_turns: 8` may remain.

- [ ] **Step 9: Commit docs and contract wording**

Run:

```bash
git add README.md AGENTS.md docs/overall-solution-architecture.md docs/implementation-roadmap.md docs/development-tracker.md docs/design-change-log.md docs/guides/configuration-guide.md docs/frontend-protocol.md docs/modules/agent-core.md docs/pi-inspired-agent-core-blueprint.md src/embedagent/config.py src/embedagent/session.py
git commit -m "docs: describe pi-style loop continuation"
```

Expected: commit succeeds.

## Task 6: Full Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
uv run pytest tests/test_agent_loop_continuation.py tests/test_query_engine_refactor.py tests/test_inprocess_adapter_frontend_api.py -v
```

Expected: tests pass.

- [ ] **Step 2: Run config, GUI runtime, and compatibility tests**

Run:

```bash
uv run pytest tests/test_config.py tests/test_gui_runtime.py tests/test_query_engine_orchestrator.py tests/test_characterization.py tests/test_exception_characterization.py -v
```

Expected: tests pass.

- [ ] **Step 3: Run the fast suite**

Run:

```bash
uv run pytest tests/ -m "not slow and not gui" -v
```

Expected: tests pass.

- [ ] **Step 4: Run lint checks**

Run:

```bash
uv run ruff check src/ tests/
uv run black --check src/ tests/
```

Expected: both commands pass.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git diff --stat HEAD~5..HEAD
git diff HEAD~5..HEAD -- src/embedagent/agent_loop.py src/embedagent/agent_loop_continuation.py src/embedagent/query_engine.py src/embedagent/inprocess_adapter.py
```

Expected: the diff shows a small internal policy module, an open-loop conversion, default `None` safety-limit propagation, and no workflow-specific policy added to Agent Core.

- [ ] **Step 6: Final commit if verification found small fixes**

If verification required fixes, commit them:

```bash
git add src tests docs README.md AGENTS.md
git commit -m "fix: stabilize pi-style loop continuation"
```

Expected: no uncommitted implementation or docs changes remain.

- [ ] **Step 7: Final status**

Run:

```bash
git status --short
```

Expected: clean worktree.

## Self-Review

- Spec coverage: The plan implements the approved Pi-style open loop, keeps `AgentLoop` small, preserves explicit `max_turns` compatibility, leaves compaction in `ContextManager`, leaves C/C++ workflow policy behind the extension boundary, preserves pending interaction and guard-stop paths, adds focused tests, and updates source-of-truth docs.
- Placeholder scan: The plan contains concrete file paths, code snippets, commands, and expected results for each task.
- Type consistency: `AgentLoopContinuationFacts`, `AgentLoopContinuationDecision`, `AgentLoopContinuationPolicy`, `DefaultAgentLoopContinuationPolicy`, and the `loop_safety_limit` naming are introduced in Task 1 and reused consistently in later tasks.
