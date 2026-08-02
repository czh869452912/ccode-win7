from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from embedagent_core.agent_effects import PreparedToolInvocation
from embedagent_core.session import Observation


@dataclass
class ToolBatch:
    parallel: bool
    actions: List[Any] = field(default_factory=list)


@dataclass
class ToolExecutionUpdate:
    action: Any
    observation: Optional[Observation] = None
    phase: str = "result"
    progress: Optional[Dict[str, Any]] = None


class StreamingToolExecutor(object):
    def __init__(
        self,
        execute_action: Callable[[Any], Observation],
        max_parallel: int = 3,
        cancel_event: Optional[threading.Event] = None,
        idle_timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.1,
        join_timeout_seconds: float = 0.05,
    ) -> None:
        self.execute_action = execute_action
        self.max_parallel = max(1, int(max_parallel or 1))
        self.cancel_event = cancel_event
        self.idle_timeout_seconds = max(0.0, float(idle_timeout_seconds or 0.0))
        self.poll_interval_seconds = max(0.01, float(poll_interval_seconds or 0.1))
        self.join_timeout_seconds = max(0.0, float(join_timeout_seconds or 0.0))
        self._discarded = False
        self._lock = threading.Lock()

    def discard(self) -> None:
        with self._lock:
            self._discarded = True

    def _is_discarded(self) -> bool:
        with self._lock:
            return self._discarded

    def run_batch(self, batch: ToolBatch) -> List[ToolExecutionUpdate]:
        if not batch.actions:
            return []
        if not batch.parallel or len(batch.actions) == 1:
            return self._run_serial(batch.actions)
        return self._run_parallel(batch.actions)

    def _run_serial(self, actions: List[Any]) -> List[ToolExecutionUpdate]:
        updates = []
        for action in actions:
            if self._is_discarded():
                updates.append(self._discarded_update(action))
                continue
            updates.append(ToolExecutionUpdate(action=action, phase="start"))
            updates.append(
                ToolExecutionUpdate(
                    action=action,
                    observation=self.execute_action(action),
                    phase="result",
                )
            )
        return updates

    def _run_parallel(self, actions: List[Any]):
        updates = queue.Queue()  # type: queue.Queue
        sibling_error = threading.Event()
        threads = []
        started_count = 0
        pending_results = {}  # type: Dict[str, ToolExecutionUpdate]
        next_result_index = 0
        yielded_results = 0
        action_state = {}  # type: Dict[str, Dict[str, bool]]
        action_state_lock = threading.Lock()
        idle_deadline = (
            time.time() + self.idle_timeout_seconds if self.idle_timeout_seconds > 0 else 0.0
        )

        for action in actions:
            action_state[self._action_key(action)] = {"started": False, "finished": False}

        def runner(action: Any) -> None:
            action_key = self._action_key(action)
            if (
                self._is_discarded()
                or sibling_error.is_set()
                or (self.cancel_event is not None and self.cancel_event.is_set())
            ):
                updates.put(self._discarded_update(action))
                return
            with action_state_lock:
                action_state[action_key]["started"] = True
            updates.put(ToolExecutionUpdate(action=action, phase="start"))
            try:
                observation = self.execute_action(action)
            except (RuntimeError, ValueError, TypeError) as exc:
                observation = Observation(
                    tool_name=self._action_name(action),
                    success=False,
                    error=str(exc),
                    data={"error_kind": "tool_error", "retryable": False},
                )
            with action_state_lock:
                action_state[action_key]["finished"] = True
            updates.put(
                ToolExecutionUpdate(
                    action=action,
                    observation=observation,
                    phase="result",
                )
            )
            if not observation.success:
                sibling_error.set()

        def start_next() -> None:
            nonlocal started_count
            if started_count >= len(actions):
                return
            action = actions[started_count]
            started_count += 1
            thread = threading.Thread(target=runner, args=(action,))
            thread.daemon = True
            threads.append(thread)
            thread.start()

        for _ in range(min(self.max_parallel, len(actions))):
            start_next()

        while yielded_results < len(actions):
            try:
                update = updates.get(timeout=self.poll_interval_seconds)
            except queue.Empty:
                synthetic_updates = []
                if self.cancel_event is not None and self.cancel_event.is_set():
                    self.discard()
                    synthetic_updates = self._finalize_incomplete_updates(
                        actions,
                        action_state,
                        action_state_lock,
                        reason="cancel",
                    )
                elif idle_deadline and time.time() >= idle_deadline:
                    self.discard()
                    synthetic_updates = self._finalize_incomplete_updates(
                        actions,
                        action_state,
                        action_state_lock,
                        reason="timeout",
                    )
                if not synthetic_updates:
                    continue
                for synthetic in synthetic_updates:
                    pending_results[self._action_key(synthetic.action)] = synthetic
            else:
                if update.phase == "start":
                    yield update
                    if idle_deadline:
                        idle_deadline = time.time() + self.idle_timeout_seconds
                    continue
                pending_results[self._action_key(update.action)] = update
                if idle_deadline:
                    idle_deadline = time.time() + self.idle_timeout_seconds
            while next_result_index < len(actions):
                expected_key = self._action_key(actions[next_result_index])
                if expected_key not in pending_results:
                    break
                current = pending_results.pop(expected_key)
                yield current
                next_result_index += 1
                yielded_results += 1
                if sibling_error.is_set() or self._is_discarded():
                    self.discard()
                    while started_count < len(actions):
                        action = actions[started_count]
                        started_count += 1
                        pending_results[self._action_key(action)] = self._discarded_update(action)
                    continue
                start_next()

        for thread in threads:
            thread.join(self.join_timeout_seconds)

    def _discarded_update(self, action: Any) -> ToolExecutionUpdate:
        return ToolExecutionUpdate(
            action=action,
            observation=Observation(
                tool_name=self._action_name(action),
                success=False,
                error="tool execution discarded",
                data={"error_kind": "discarded", "retryable": False},
            ),
            phase="result",
        )

    def _interrupted_update(self, action: Any) -> ToolExecutionUpdate:
        return ToolExecutionUpdate(
            action=action,
            observation=Observation(
                tool_name=self._action_name(action),
                success=False,
                error="tool execution interrupted",
                data={"error_kind": "interrupted", "retryable": False},
            ),
            phase="result",
        )

    def _timeout_update(self, action: Any) -> ToolExecutionUpdate:
        return ToolExecutionUpdate(
            action=action,
            observation=Observation(
                tool_name=self._action_name(action),
                success=False,
                error="tool execution timed out",
                data={"error_kind": "timeout", "retryable": False},
            ),
            phase="result",
        )

    def _finalize_incomplete_updates(
        self,
        actions: List[Any],
        action_state: Dict[str, Dict[str, bool]],
        action_state_lock: threading.Lock,
        reason: str,
    ) -> List[ToolExecutionUpdate]:
        updates = []
        with action_state_lock:
            for action in actions:
                state = action_state.get(self._action_key(action)) or {}
                if state.get("finished"):
                    continue
                state["finished"] = True
                if state.get("started"):
                    if reason == "cancel":
                        updates.append(self._interrupted_update(action))
                    else:
                        updates.append(self._timeout_update(action))
                else:
                    updates.append(self._discarded_update(action))
        return updates

    def _action_key(self, action: Any) -> str:
        if isinstance(action, PreparedToolInvocation):
            return action.invocation_id
        return str(action.call_id)

    def _action_name(self, action: Any) -> str:
        if isinstance(action, PreparedToolInvocation):
            return action.effective_action.name
        return str(action.name)


def partition_tool_actions(
    actions: List[Any],
    capability_lookup: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> List[ToolBatch]:
    batches = []
    current = None  # type: Optional[ToolBatch]
    for action in actions:
        if isinstance(action, PreparedToolInvocation):
            is_parallel = bool(action.read_only) and bool(action.concurrency_safe)
        else:
            capabilities = (
                capability_lookup(action.name) if capability_lookup is not None else {}
            ) or {}
            is_parallel = bool(capabilities.get("read_only")) and bool(
                capabilities.get("concurrency_safe")
            )
        if current is None or current.parallel != is_parallel:
            current = ToolBatch(parallel=is_parallel, actions=[action])
            batches.append(current)
        else:
            current.actions.append(action)
    return batches
