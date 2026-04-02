from __future__ import annotations

import queue
import threading
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
    ) -> None:
        self.execute_action = execute_action
        self.max_parallel = max(1, int(max_parallel or 1))
        self.cancel_event = cancel_event
        self._discarded = False
        self._lock = threading.Lock()

    def discard(self) -> None:
        with self._lock:
            self._discarded = True

    def run_batch(self, batch: ToolBatch) -> List[ToolExecutionUpdate]:
        if not batch.actions:
            return []
        if not batch.parallel or len(batch.actions) == 1:
            return self._run_serial(batch.actions)
        return self._run_parallel(batch.actions)

    def _run_serial(self, actions: List[Action]) -> List[ToolExecutionUpdate]:
        updates = []
        for action in actions:
            if self._discarded:
                updates.append(
                    ToolExecutionUpdate(
                        action=action,
                        observation=Observation(
                            tool_name=action.name,
                            success=False,
                            error="tool execution discarded",
                            data={"error_kind": "discarded", "retryable": False},
                        ),
                    )
                )
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

        def runner(action: Action) -> None:
            with semaphore:
                if self._discarded or sibling_error.is_set() or (self.cancel_event is not None and self.cancel_event.is_set()):
                    updates.put(
                        ToolExecutionUpdate(
                            action=action,
                            observation=Observation(
                                tool_name=action.name,
                                success=False,
                                error="tool execution discarded",
                                data={"error_kind": "discarded", "retryable": False},
                            ),
                            phase="result",
                        )
                    )
                    return
                updates.put(ToolExecutionUpdate(action=action, phase="start"))
                observation = self.execute_action(action)
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
            update = updates.get()
            if update.phase == "start":
                yield update
                continue
            pending_results[update.action.call_id] = update
            while next_result_index < len(actions):
                expected_call_id = actions[next_result_index].call_id
                if expected_call_id not in pending_results:
                    break
                yield pending_results.pop(expected_call_id)
                next_result_index += 1
                yielded_results += 1

        for thread in threads:
            thread.join()


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
