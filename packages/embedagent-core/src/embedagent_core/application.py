from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from embedagent_core.registration_scope import RegistrationScope

_REGISTRATION_ERRORS = (
    AttributeError,
    ImportError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


class ApplicationConfigurationError(ValueError):
    """Raised when selected application runtime semantics are incomplete."""


@dataclass(frozen=True)
class ApplicationRuntimeContribution(object):
    """Workflow-neutral runtime contribution owned by a selected application."""

    application_id: str
    label: str
    runtime_definition_factory: Callable[[], Any]
    application_state_factory: Optional[Callable[[], Any]] = None
    workspace_contribution_factory: Optional[Callable[[], Any]] = None
    capabilities: Tuple[str, ...] = field(default_factory=tuple)
    workflow_package_ids: Tuple[str, ...] = field(default_factory=tuple)
    empty_state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        application_id = str(self.application_id or "").strip()
        label = str(self.label or "").strip()
        if not application_id or not label:
            raise ApplicationConfigurationError(
                "application runtime contribution identity is required"
            )
        if not callable(self.runtime_definition_factory):
            raise TypeError("application runtime definition factory is required")
        capabilities = tuple(str(item or "").strip() for item in self.capabilities or ())
        if any(not item for item in capabilities) or len(capabilities) != len(set(capabilities)):
            raise ValueError("application runtime capabilities must be unique and nonempty")
        workflow_package_ids = tuple(
            str(item or "").strip() for item in self.workflow_package_ids or ()
        )
        if any(not item for item in workflow_package_ids) or len(workflow_package_ids) != len(
            set(workflow_package_ids)
        ):
            raise ValueError("application workflow package ids must be unique and nonempty")
        object.__setattr__(self, "application_id", application_id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "workflow_package_ids", workflow_package_ids)
        object.__setattr__(self, "empty_state", dict(self.empty_state or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


class ApplicationRegistrar(object):
    """Focused registration sink for one selected application plugin."""

    def __init__(
        self,
        extension_host: Any,
        shell_registry: Any,
        runtime_registry: Optional[Any] = None,
        scope: Optional[RegistrationScope] = None,
    ) -> None:
        self._extension_host = extension_host
        self._shell_registry = shell_registry
        self._runtime_registry = runtime_registry
        self._scope = scope or RegistrationScope("application")
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
            try:
                disposer()
            finally:
                self._source_ids.discard(source_id)

        return self._scope.register(dispose_once)

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

        def noop_disposer() -> None:
            return None

        registry_disposer = noop_disposer
        shell_disposer = noop_disposer
        if registry is not None:
            register = getattr(registry, "register", None)
            if not callable(register):
                self._runtime_contributions.pop(application_id, None)
                raise TypeError("application runtime registry is invalid")
            try:
                registry_disposer = register(contribution, source)
            except _REGISTRATION_ERRORS:
                self._runtime_contributions.pop(application_id, None)
                raise
            if not callable(registry_disposer):
                self._runtime_contributions.pop(application_id, None)
                raise TypeError("application runtime registry did not return a disposer")
        register_application = getattr(self._shell_registry, "register_application", None)
        try:
            if callable(register_application):
                shell_disposer = register_application(application_id)
            if not callable(shell_disposer):
                raise TypeError("shell application registry did not return a disposer")
        except _REGISTRATION_ERRORS:
            try:
                registry_disposer()
            finally:
                self._runtime_contributions.pop(application_id, None)
            raise

        def remove() -> None:
            self._runtime_contributions.pop(application_id, None)
            try:
                shell_disposer()
            finally:
                registry_disposer()

        return self._append_disposer(remove, source)

    def runtime_contributions(self) -> Tuple[ApplicationRuntimeContribution, ...]:
        return tuple(self._runtime_contributions.values())

    def dispose(self) -> None:
        try:
            self._scope.dispose()
        finally:
            self._source_ids.clear()
