from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AgentEvent(object):
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventHandlerRegistration(object):
    event_type: str
    source_id: str
    source_type: str
    handler: Callable[[AgentEvent, Any], Any]
    kind: str = "reducer"
    fail_closed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventDispatchResult(object):
    reducer_results: List[Dict[str, Any]] = field(default_factory=list)
    observer_results: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


class AgentEventDispatchError(RuntimeError):
    def __init__(self, original: Exception, diagnostics: List[Dict[str, Any]]) -> None:
        super(AgentEventDispatchError, self).__init__(str(original))
        self.original = original
        self.diagnostics = list(diagnostics or [])


class AgentEventBus(object):
    """Source-aware dispatch boundary for internal agent events."""

    def __init__(self) -> None:
        self._reducers = []  # type: List[EventHandlerRegistration]
        self._observers = []  # type: List[EventHandlerRegistration]

    def register_reducer(
        self,
        event_type: str,
        source_id: str,
        source_type: str,
        reducer: Callable[[AgentEvent, Any], Any],
        fail_closed: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._reducers.append(
            EventHandlerRegistration(
                event_type=str(event_type or ""),
                source_id=str(source_id or ""),
                source_type=str(source_type or "extension"),
                handler=reducer,
                kind="reducer",
                fail_closed=bool(fail_closed),
                metadata=dict(metadata or {}),
            )
        )

    def register_observer(
        self,
        event_type: str,
        source_id: str,
        source_type: str,
        observer: Callable[[AgentEvent, Any], Any],
        fail_closed: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._observers.append(
            EventHandlerRegistration(
                event_type=str(event_type or ""),
                source_id=str(source_id or ""),
                source_type=str(source_type or "extension"),
                handler=observer,
                kind="observer",
                fail_closed=bool(fail_closed),
                metadata=dict(metadata or {}),
            )
        )

    def dispatch(
        self,
        event: AgentEvent,
        context: Any = None,
        reducer_stop: Optional[Callable[[Any], bool]] = None,
    ) -> EventDispatchResult:
        result = EventDispatchResult()
        event_type = str(event.event_type or "")
        for registration in list(self._observers):
            if registration.event_type != event_type:
                continue
            self._call_registration(registration, event, context, result)
        for registration in list(self._reducers):
            if registration.event_type != event_type:
                continue
            self._call_registration(registration, event, context, result)
            if result.reducer_results and reducer_stop is not None:
                value = result.reducer_results[-1].get("value")
                if bool(reducer_stop(value)):
                    break
        return result

    def _call_registration(
        self,
        registration: EventHandlerRegistration,
        event: AgentEvent,
        context: Any,
        result: EventDispatchResult,
    ) -> None:
        try:
            value = registration.handler(event, context)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            metadata = dict(event.metadata)
            metadata.update(dict(registration.metadata))
            diagnostic = {
                "source_id": registration.source_id,
                "source_type": registration.source_type,
                "event_type": registration.event_type,
                "kind": registration.kind,
                "error": str(exc),
                "metadata": metadata,
            }
            result.diagnostics.append(diagnostic)
            if registration.fail_closed:
                raise AgentEventDispatchError(exc, result.diagnostics)
            return
        if value is None:
            return
        if registration.kind == "observer":
            return
        item = {
            "source_id": registration.source_id,
            "source_type": registration.source_type,
            "value": value,
            "metadata": dict(registration.metadata),
        }
        result.reducer_results.append(item)
