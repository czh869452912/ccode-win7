from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from embedagent.session import Action, Observation


@dataclass
class ToolBatch:
    parallel: bool
    actions: List[Action] = field(default_factory=list)


@dataclass
class ToolExecutionUpdate:
    action: Action
    observation: Optional[Observation] = None
    phase: str = "result"
    progress: Optional[Dict[str, Any]] = None


class StreamingToolExecutor(object):
    def __init__(
        self,
        execute_action: Callable[[Action], Observation],
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

    def _run_serial(self, actions: List[Action]) -> List[ToolExecutionUpdate]:
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

    def _run_parallel(self, actions: List[Action]):
        updates = queue.Queue()  # type: queue.Queue
        sibling_error = threading.Event()
        semaphore = threading.Semaphore(self.max_parallel)
        threads = []
        pending_results = {}  # type: Dict[str, ToolExecutionUpdate]
        next_result_index = 0
        yielded_results = 0
        action_state = {}  # type: Dict[str, Dict[str, bool]]
        action_state_lock = threading.Lock()
        idle_deadline = (
            time.time() + self.idle_timeout_seconds
            if self.idle_timeout_seconds > 0
            else 0.0
        )

        for action in actions:
            action_state[action.call_id] = {"started": False, "finished": False}

        def runner(action: Action) -> None:
            with semaphore:
                if self._is_discarded() or sibling_error.is_set() or (self.cancel_event is not None and self.cancel_event.is_set()):
                    updates.put(self._discarded_update(action))
                    return
                with action_state_lock:
                    action_state[action.call_id]["started"] = True
                updates.put(ToolExecutionUpdate(action=action, phase="start"))
                try:
                    observation = self.execute_action(action)
                except Exception as exc:
                    observation = Observation(
                        tool_name=action.name,
                        success=False,
                        error=str(exc),
                        data={"error_kind": "tool_error", "retryable": False},
                    )
                with action_state_lock:
                    action_state[action.call_id]["finished"] = True
                updates.put(
                    ToolExecutionUpdate(
                        action=action,
                        observation=observation,
                        phase="result",
                    )
                )
                if not observation.success:
                    sibling_error.set()

        for action in actions:
            thread = threading.Thread(target=runner, args=(action,))
            thread.daemon = True
            threads.append(thread)

        for thread in threads:
            thread.start()

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
                    pending_results[synthetic.action.call_id] = synthetic
            else:
                if update.phase == "start":
                    yield update
                    if idle_deadline:
                        idle_deadline = time.time() + self.idle_timeout_seconds
                    continue
                pending_results[update.action.call_id] = update
                if idle_deadline:
                    idle_deadline = time.time() + self.idle_timeout_seconds
            while next_result_index < len(actions):
                expected_call_id = actions[next_result_index].call_id
                if expected_call_id not in pending_results:
                    break
                yield pending_results.pop(expected_call_id)
                next_result_index += 1
                yielded_results += 1

        for thread in threads:
            thread.join(self.join_timeout_seconds)

    def _discarded_update(self, action: Action) -> ToolExecutionUpdate:
        return ToolExecutionUpdate(
            action=action,
            observation=Observation(
                tool_name=action.name,
                success=False,
                error="tool execution discarded",
                data={"error_kind": "discarded", "retryable": False},
            ),
            phase="result",
        )

    def _interrupted_update(self, action: Action) -> ToolExecutionUpdate:
        return ToolExecutionUpdate(
            action=action,
            observation=Observation(
                tool_name=action.name,
                success=False,
                error="tool execution interrupted",
                data={"error_kind": "interrupted", "retryable": False},
            ),
            phase="result",
        )

    def _timeout_update(self, action: Action) -> ToolExecutionUpdate:
        return ToolExecutionUpdate(
            action=action,
            observation=Observation(
                tool_name=action.name,
                success=False,
                error="tool execution timed out",
                data={"error_kind": "timeout", "retryable": False},
            ),
            phase="result",
        )

    def _finalize_incomplete_updates(
        self,
        actions: List[Action],
        action_state: Dict[str, Dict[str, bool]],
        action_state_lock: threading.Lock,
        reason: str,
    ) -> List[ToolExecutionUpdate]:
        updates = []
        with action_state_lock:
            for action in actions:
                state = action_state.get(action.call_id) or {}
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


def partition_tool_actions(
    actions: List[Action],
    capability_lookup: Callable[[str], Dict[str, Any]],
) -> List[ToolBatch]:
    batches = []
    current = None  # type: Optional[ToolBatch]
    for action in actions:
        capabilities = capability_lookup(action.name) or {}
        is_parallel = bool(capabilities.get("read_only")) and bool(capabilities.get("concurrency_safe"))
        if current is None or current.parallel != is_parallel:
            current = ToolBatch(parallel=is_parallel, actions=[action])
            batches.append(current)
        else:
            current.actions.append(action)
    return batches
