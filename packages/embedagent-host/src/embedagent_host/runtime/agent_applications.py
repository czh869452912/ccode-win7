from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from embedagent_core import (
    ApplicationConfigurationError,
    ApplicationRuntimeContribution,
    ApplicationRuntimePolicy,
    RuntimeDefinition,
)
from embedagent_core.extensions import ExtensionManager
from embedagent_core.profile import AgentProfile

from embedagent_host.runtime.profiles import (
    generic_agent_profile,
    generic_runtime_definition,
    html_agent_profile,
    html_runtime_definition,
    python_agent_profile,
    python_runtime_definition,
)

GENERIC_AGENT_APPLICATION_ID = "embedagent.generic"
PYTHON_AGENT_APPLICATION_ID = "embedagent.python"
HTML_AGENT_APPLICATION_ID = "embedagent.html"


@dataclass(frozen=True)
class AgentApplicationManifest:
    application_id: str
    label: str
    profile_id: str
    workflow_package_ids: Tuple[str, ...] = field(default_factory=tuple)
    source_type: str = "builtin"
    source_id: str = ""
    default: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "applicationId": self.application_id,
            "label": self.label,
            "profileId": self.profile_id,
            "workflowPackageIds": list(self.workflow_package_ids),
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "default": bool(self.default),
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentApplication:
    application_id: str
    label: str
    profile: Optional[AgentProfile]
    extension_manager: ExtensionManager
    application_state: Any = None
    manifest: Optional[AgentApplicationManifest] = None
    runtime_definition: Optional[RuntimeDefinition] = None
    workflow_refreshers: Tuple[Any, ...] = field(default_factory=tuple)
    workspace_profile_detectors: Tuple[Any, ...] = field(default_factory=tuple)

    def refresh_managed_session(
        self,
        state: Any,
        workspace: str,
        observations: Any = None,
    ) -> None:
        for refresher in self.workflow_refreshers:
            refresh = getattr(refresher, "refresh_managed_session", None)
            if callable(refresh):
                refresh(state, workspace, observations=observations)


@dataclass(frozen=True)
class AgentApplicationRecord:
    application_id: str
    label: str
    profile_id: str
    application_state_factory: Any = None
    runtime_factory: Any = None
    workflow_package_ids: Tuple[str, ...] = field(default_factory=tuple)
    workspace_profile_detectors_factory: Any = None
    source_type: str = "builtin"
    source_id: str = ""
    default: bool = False
    empty_state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_manifest(self) -> AgentApplicationManifest:
        return AgentApplicationManifest(
            application_id=self.application_id,
            label=self.label,
            profile_id=self.profile_id,
            workflow_package_ids=tuple(self.workflow_package_ids),
            source_type=self.source_type,
            source_id=self.source_id,
            default=bool(self.default),
            metadata=dict(self.metadata or {}),
        )


@dataclass(frozen=True)
class AgentApplicationRegistry:
    application_records: Tuple[AgentApplicationRecord, ...]
    default_application_id: str = ""

    def __post_init__(self) -> None:
        records = tuple(self.application_records or ())
        object.__setattr__(self, "application_records", records)
        default_id = str(self.default_application_id or "").strip()
        if not default_id:
            for record in records:
                if record.default:
                    default_id = record.application_id
                    break
        if not default_id and records:
            default_id = records[0].application_id
        object.__setattr__(self, "default_application_id", default_id)

    def record_by_id(self, application_id: str = "") -> AgentApplicationRecord:
        if not isinstance(application_id, str) or not application_id.strip():
            raise ApplicationConfigurationError("selected application id is required")
        requested = application_id.strip()
        for record in self.application_records:
            if requested == record.application_id:
                return record
        raise ApplicationConfigurationError(
            "selected application is not registered: %s" % requested
        )

    def manifests(self) -> List[AgentApplicationManifest]:
        return [record.to_manifest() for record in self.application_records]


class ApplicationRuntimeContributionRegistry(object):
    """Collect selected plugin contributions without importing workflow packages."""

    def __init__(self) -> None:
        self._contributions = {}

    def register(
        self,
        contribution: ApplicationRuntimeContribution,
        source_id: str,
    ):
        if not isinstance(contribution, ApplicationRuntimeContribution):
            raise TypeError("application runtime contribution is invalid")
        application_id = contribution.application_id
        if application_id in self._contributions:
            raise ValueError("duplicate_application_runtime:%s" % application_id)
        self._contributions[application_id] = (str(source_id or ""), contribution)

        def dispose() -> None:
            current = self._contributions.get(application_id)
            if current is not None and current[1] is contribution:
                self._contributions.pop(application_id, None)

        return dispose

    def contributions(self):
        return tuple(item[1] for item in self._contributions.values())


BUILTIN_AGENT_APPLICATION_RECORDS = (
    AgentApplicationRecord(
        application_id=GENERIC_AGENT_APPLICATION_ID,
        label="Generic Agent",
        profile_id=GENERIC_AGENT_APPLICATION_ID,
        application_state_factory=generic_agent_profile,
        runtime_factory=generic_runtime_definition,
        source_type="builtin",
        source_id="embedagent_host.runtime.profiles",
        empty_state={
            "scenario_label": "Generic workspace",
            "primary": "Open a local project",
            "secondary": "The selected agent will use generic project modes after workspace activation.",
            "path_placeholder": "Path to project",
        },
        metadata={"domain": "generic"},
    ),
    AgentApplicationRecord(
        application_id=PYTHON_AGENT_APPLICATION_ID,
        label="Python Agent",
        profile_id=PYTHON_AGENT_APPLICATION_ID,
        application_state_factory=python_agent_profile,
        runtime_factory=python_runtime_definition,
        source_type="builtin",
        source_id="embedagent_host.runtime.profiles",
        empty_state={
            "scenario_label": "Python workspace",
            "primary": "Open a Python project",
            "secondary": "The selected agent will use Python project modes after workspace activation.",
            "path_placeholder": "Path to Python project",
        },
        metadata={"domain": "python"},
    ),
    AgentApplicationRecord(
        application_id=HTML_AGENT_APPLICATION_ID,
        label="HTML Agent",
        profile_id=HTML_AGENT_APPLICATION_ID,
        application_state_factory=html_agent_profile,
        runtime_factory=html_runtime_definition,
        source_type="builtin",
        source_id="embedagent_host.runtime.profiles",
        empty_state={
            "scenario_label": "HTML/Web workspace",
            "primary": "Open an HTML/Web project",
            "secondary": "The selected agent will use frontend project modes after workspace activation.",
            "path_placeholder": "Path to HTML/Web project",
        },
        metadata={"domain": "html"},
    ),
)


def base_agent_application_registry() -> AgentApplicationRegistry:
    return AgentApplicationRegistry(
        application_records=tuple(BUILTIN_AGENT_APPLICATION_RECORDS),
        default_application_id=GENERIC_AGENT_APPLICATION_ID,
    )


def runtime_contribution_for_record(
    record: AgentApplicationRecord,
) -> ApplicationRuntimeContribution:
    if not isinstance(record, AgentApplicationRecord):
        raise TypeError("agent application record is invalid")

    runtime_factory = record.runtime_factory
    if not callable(runtime_factory):
        raise ApplicationConfigurationError(
            "application runtime contribution is missing: %s" % record.application_id
        )

    metadata = dict(record.metadata or {})
    if record.profile_id:
        metadata["profile_id"] = record.profile_id
    if record.source_id:
        metadata.setdefault("source_id", record.source_id)
    return ApplicationRuntimeContribution(
        application_id=record.application_id,
        label=record.label,
        runtime_definition_factory=runtime_factory,
        application_state_factory=record.application_state_factory,
        workspace_contribution_factory=record.workspace_profile_detectors_factory,
        workflow_package_ids=tuple(record.workflow_package_ids),
        empty_state=dict(record.empty_state or {}),
        metadata=metadata,
    )


def application_registry_from_runtime_contributions(
    contributions,
    default_application_id: str = "",
) -> AgentApplicationRegistry:
    records = []
    for contribution in tuple(contributions or ()):
        if not isinstance(contribution, ApplicationRuntimeContribution):
            raise TypeError("application runtime contribution is invalid")
        metadata = dict(contribution.metadata or {})
        state_factory = contribution.application_state_factory
        profile_id = str(metadata.get("profile_id") or "")
        records.append(
            AgentApplicationRecord(
                application_id=contribution.application_id,
                label=contribution.label,
                profile_id=profile_id,
                application_state_factory=state_factory,
                runtime_factory=contribution.runtime_definition_factory,
                workflow_package_ids=tuple(contribution.workflow_package_ids),
                workspace_profile_detectors_factory=contribution.workspace_contribution_factory,
                source_type="application",
                source_id=str(metadata.get("source_id") or "application.plugin"),
                default=not records,
                empty_state=dict(contribution.empty_state or {}),
                metadata=metadata,
            )
        )
    if not records:
        raise ValueError("selected application contributions are empty")
    return AgentApplicationRegistry(
        application_records=tuple(records),
        default_application_id=str(default_application_id or records[0].application_id),
    )


def _require_registry(
    registry: Optional[AgentApplicationRegistry] = None,
) -> AgentApplicationRegistry:
    if not isinstance(registry, AgentApplicationRegistry):
        raise ApplicationConfigurationError("selected application registry is required")
    return registry


def _record_by_id(
    application_id: str,
    registry: Optional[AgentApplicationRegistry] = None,
) -> AgentApplicationRecord:
    return _require_registry(registry).record_by_id(application_id)


def _invoke_application_factory(
    factory: Any,
    factory_kind: str,
    application_id: str,
) -> Any:
    try:
        return factory()
    except ApplicationConfigurationError:
        raise
    except Exception as error:
        raise ApplicationConfigurationError(
            "application %s factory failed: %s" % (factory_kind, application_id)
        ) from error


def _application_state_for_record(record: AgentApplicationRecord) -> Any:
    factory = record.application_state_factory
    if not callable(factory):
        return None
    return _invoke_application_factory(factory, "state", record.application_id)


def require_application_identity(application_id: Any) -> str:
    if not isinstance(application_id, str) or not application_id.strip():
        raise ApplicationConfigurationError("selected application id is required")
    return application_id.strip()


def require_application_runtime_definition(
    definition: Any,
    application_id: str,
) -> RuntimeDefinition:
    if not isinstance(definition, RuntimeDefinition):
        raise ApplicationConfigurationError(
            "application runtime definition is invalid: %s" % application_id
        )
    policy = definition.application_policy
    if not isinstance(policy, ApplicationRuntimePolicy):
        raise ApplicationConfigurationError(
            "application runtime policy is invalid: %s" % application_id
        )
    default_mode = policy.default_mode
    if not isinstance(default_mode, str) or not default_mode.strip():
        raise ApplicationConfigurationError(
            "application default mode is invalid: %s" % application_id
        )
    required_policy_methods = (
        ("mode_tool_policy", ("allowed_tools_for",)),
        ("write_path_policy", ("is_path_writable",)),
        (
            "mode_runtime_policy",
            (
                "default_mode",
                "require_mode",
                "build_system_prompt",
                "parse_mode_switch_request",
            ),
        ),
    )
    for policy_name, method_names in required_policy_methods:
        policy_value = getattr(policy, policy_name, None)
        if policy_value is None or any(
            not callable(getattr(policy_value, method_name, None)) for method_name in method_names
        ):
            raise ApplicationConfigurationError(
                "application %s is invalid: %s" % (policy_name, application_id)
            )
    mode_runtime_policy = policy.mode_runtime_policy
    try:
        runtime_default_mode = mode_runtime_policy.default_mode()
    except Exception as error:
        raise ApplicationConfigurationError(
            "application mode runtime default failed: %s" % application_id
        ) from error
    if not isinstance(runtime_default_mode, str) or not runtime_default_mode.strip():
        raise ApplicationConfigurationError(
            "application mode runtime default is invalid: %s" % application_id
        )
    effective_default_mode = runtime_default_mode.strip()
    if effective_default_mode != default_mode.strip():
        raise ApplicationConfigurationError(
            "application mode runtime default is inconsistent: %s" % application_id
        )
    try:
        default_mode_definition = mode_runtime_policy.require_mode(effective_default_mode)
    except Exception as error:
        raise ApplicationConfigurationError(
            "application default mode resolution failed: %s" % application_id
        ) from error
    if not isinstance(default_mode_definition, dict):
        raise ApplicationConfigurationError(
            "application default mode definition is invalid: %s" % application_id
        )
    resolved_slug = default_mode_definition.get("slug")
    if not isinstance(resolved_slug, str) or not resolved_slug.strip():
        raise ApplicationConfigurationError(
            "application default mode slug is invalid: %s" % application_id
        )
    if resolved_slug.strip() != effective_default_mode:
        raise ApplicationConfigurationError(
            "application default mode resolution is inconsistent: %s" % application_id
        )
    return definition


def _build_application(
    record: AgentApplicationRecord,
    tools: Any,
) -> AgentApplication:
    manifest = record.to_manifest()
    runtime_factory = record.runtime_factory
    if not callable(runtime_factory):
        raise ApplicationConfigurationError(
            "application runtime contribution is missing: %s" % record.application_id
        )
    definition = require_application_runtime_definition(
        _invoke_application_factory(runtime_factory, "runtime", record.application_id),
        record.application_id,
    )
    application_state = _application_state_for_record(record)
    profile = application_state if isinstance(application_state, AgentProfile) else None
    extensions = list(definition.extensions or ())
    for extension in extensions:
        if hasattr(extension, "tools") and getattr(extension, "tools", None) is None:
            extension.tools = tools
    extension_manager = ExtensionManager(extensions)
    detectors_factory = record.workspace_profile_detectors_factory
    detectors = (
        _invoke_application_factory(detectors_factory, "workspace detector", record.application_id)
        if callable(detectors_factory)
        else ()
    )
    try:
        detector_values = tuple(detectors or ())
    except TypeError as error:
        raise ApplicationConfigurationError(
            "application workspace detector result is invalid: %s" % record.application_id
        ) from error
    return AgentApplication(
        application_id=manifest.application_id,
        label=manifest.label,
        profile=profile,
        extension_manager=extension_manager,
        application_state=application_state,
        manifest=manifest,
        runtime_definition=definition,
        workflow_refreshers=tuple(extensions),
        workspace_profile_detectors=detector_values,
    )


def generic_agent_application_manifest(
    registry: Optional[AgentApplicationRegistry] = None,
) -> AgentApplicationManifest:
    return _record_by_id(GENERIC_AGENT_APPLICATION_ID, registry=registry).to_manifest()


def python_agent_application_manifest(
    registry: Optional[AgentApplicationRegistry] = None,
) -> AgentApplicationManifest:
    return _record_by_id(PYTHON_AGENT_APPLICATION_ID, registry=registry).to_manifest()


def html_agent_application_manifest(
    registry: Optional[AgentApplicationRegistry] = None,
) -> AgentApplicationManifest:
    return _record_by_id(HTML_AGENT_APPLICATION_ID, registry=registry).to_manifest()


def available_agent_application_manifests(
    registry: Optional[AgentApplicationRegistry] = None,
) -> List[AgentApplicationManifest]:
    return _require_registry(registry).manifests()


def _copy_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _copy_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_copy_value(item) for item in value]
    return value


def _application_descriptor_payload(
    record: AgentApplicationRecord,
    active: bool = False,
) -> Dict[str, Any]:
    payload = record.to_manifest().to_dict()
    payload["active"] = bool(active)
    return payload


def application_descriptor_payload(manifest: Any, active: bool = False) -> Dict[str, Any]:
    """Serialize a build-time application manifest without synthesizing modes."""
    if isinstance(manifest, AgentApplicationRecord):
        payload = _application_descriptor_payload(manifest, active=active)
        payload["capabilities"] = []
        return payload
    to_dict = getattr(manifest, "to_dict", None)
    if not callable(to_dict):
        raise TypeError("application manifest must provide to_dict")
    raw = dict(to_dict())
    application_id = str(raw.get("application_id") or raw.get("id") or "").strip()
    label = str(raw.get("label") or application_id).strip()
    if not application_id or not label:
        raise ValueError("application manifest identity is required")
    capabilities = list(getattr(manifest, "capabilities", ()) or ())
    return {
        "id": application_id,
        "label": label,
        "active": bool(active),
        "capabilities": capabilities,
        "runtime_requirements": list(getattr(manifest, "runtime_requirements", ()) or ()),
        "distribution_id": str(raw.get("distribution_id") or ""),
        "registration_entry": str(raw.get("registration_entry") or ""),
    }


def agent_application_capability_payload(
    application_id: str = "",
    registry: Optional[AgentApplicationRegistry] = None,
) -> Dict[str, Any]:
    selected_registry = _require_registry(registry)
    selected = selected_registry.record_by_id(application_id)
    selected_id = selected.application_id
    return {
        "agentApplication": _application_descriptor_payload(selected, active=True),
        "agentApplications": [
            _application_descriptor_payload(
                record,
                active=record.application_id == selected_id,
            )
            for record in selected_registry.application_records
        ],
        "emptyState": _copy_value(selected.empty_state),
    }


def build_agent_application(
    application_id: str,
    tools: Any,
    registry: Optional[AgentApplicationRegistry] = None,
) -> AgentApplication:
    record = _record_by_id(application_id, registry=registry)
    return _build_application(record, tools)
