from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple


@dataclass(frozen=True)
class ApplicationRuntimeContribution(object):
    """Workflow-neutral runtime contribution owned by a selected application."""

    application_id: str
    label: str
    runtime_definition_factory: Callable[[], Any]
    workspace_contribution_factory: Optional[Callable[[], Any]] = None
    capabilities: Tuple[str, ...] = field(default_factory=tuple)
    empty_state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        application_id = str(self.application_id or "").strip()
        label = str(self.label or "").strip()
        if not application_id or not label:
            raise ValueError("application runtime contribution identity is required")
        if not callable(self.runtime_definition_factory):
            raise TypeError("application runtime definition factory is required")
        capabilities = tuple(str(item or "").strip() for item in self.capabilities or ())
        if any(not item for item in capabilities) or len(capabilities) != len(set(capabilities)):
            raise ValueError("application runtime capabilities must be unique and nonempty")
        object.__setattr__(self, "application_id", application_id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "empty_state", dict(self.empty_state or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


class ApplicationRegistrar(object):
    """Focused registration sink for one selected application plugin."""

    def __init__(
        self,
        extension_host: Any,
        shell_registry: Any,
        runtime_registry: Optional[Any] = None,
    ) -> None:
        self._extension_host = extension_host
        self._shell_registry = shell_registry
        self._runtime_registry = runtime_registry
        self._disposers = []
        self._source_ids = set()
        self._runtime_contributions = {}

    def _source(self, source_id: str) -> str:
        normalized = str(source_id or "").strip()
        if not normalized:
            raise ValueError("application source id must be nonempty")
        self._source_ids.add(normalized)
        return normalized

    def _append_disposer(self, disposer: Any, source_id: str) -> Callable[[], None]:
        if not callable(disposer):
            raise TypeError("application registration did not return a disposer")
        called = [False]

        def dispose_once() -> None:
            if called[0]:
                return
            called[0] = True
            disposer()

        self._disposers.append((source_id, dispose_once))
        return dispose_once

    def add_extension(self, extension: Any, source_id: str) -> Callable[[], None]:
        source = self._source(source_id)
        disposer = self._extension_host.register(extension, source)
        return self._append_disposer(disposer, source)

    def add_prompt_provider(self, provider: Any, source_id: str) -> Callable[[], None]:
        source = self._source(source_id)
        disposer = self._extension_host.register_prompt_provider(provider, source)
        return self._append_disposer(disposer, source)

    def add_context_provider(self, provider: Any, source_id: str) -> Callable[[], None]:
        source = self._source(source_id)
        disposer = self._extension_host.register_context_provider(provider, source)
        return self._append_disposer(disposer, source)

    def add_shell_contribution(self, contribution: Any, source_id: str) -> Callable[[], None]:
        source = self._source(source_id)
        disposer = self._shell_registry.register(contribution, source)
        return self._append_disposer(disposer, source)

    def add_runtime_contribution(
        self,
        contribution: ApplicationRuntimeContribution,
        source_id: str,
    ) -> Callable[[], None]:
        source = self._source(source_id)
        if not isinstance(contribution, ApplicationRuntimeContribution):
            raise TypeError("application runtime contribution is invalid")
        application_id = contribution.application_id
        if application_id in self._runtime_contributions:
            raise ValueError("duplicate_application_runtime:%s" % application_id)
        self._runtime_contributions[application_id] = contribution
        registry = self._runtime_registry
        if registry is not None:
            register = getattr(registry, "register", None)
            if not callable(register):
                self._runtime_contributions.pop(application_id, None)
                raise TypeError("application runtime registry is invalid")
            try:
                disposer = register(contribution, source)
            except Exception:
                self._runtime_contributions.pop(application_id, None)
                raise
        else:

            def disposer() -> None:
                return None

        def remove() -> None:
            self._runtime_contributions.pop(application_id, None)
            disposer()

        return self._append_disposer(remove, source)

    def runtime_contributions(self) -> Tuple[ApplicationRuntimeContribution, ...]:
        return tuple(self._runtime_contributions.values())

    def dispose(self) -> None:
        while self._disposers:
            source_id, disposer = self._disposers.pop()
            try:
                disposer()
            finally:
                self._source_ids.discard(source_id)
