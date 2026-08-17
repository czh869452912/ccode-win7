from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from embedagent_core import ApplicationRuntimePolicy, RuntimeDefinition
from embedagent_core.extensions import ExtensionManager
from embedagent_core.profile import AgentProfile
from embedagent_core.profile_runtime import (
    AgentProfileRuntimePolicy,
    AgentProfileToolPolicy,
    AgentProfileWritePathPolicy,
)

from embedagent_host.runtime.profiles import (
    generic_agent_profile,
    html_agent_profile,
    python_agent_profile,
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
    profile: AgentProfile
    extension_manager: ExtensionManager
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
    profile_factory: Any = None
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
        requested = str(application_id or "").strip() or self.default_application_id
        for record in self.application_records:
            if requested == record.application_id:
                return record
        raise ValueError("Unknown agent application %r" % (application_id,))

    def manifests(self) -> List[AgentApplicationManifest]:
        return [record.to_manifest() for record in self.application_records]


BUILTIN_AGENT_APPLICATION_RECORDS = (
    AgentApplicationRecord(
        application_id=GENERIC_AGENT_APPLICATION_ID,
        label="Generic Agent",
        profile_id=GENERIC_AGENT_APPLICATION_ID,
        profile_factory=generic_agent_profile,
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
        profile_factory=python_agent_profile,
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
        profile_factory=html_agent_profile,
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


def _registry_or_base(
    registry: Optional[AgentApplicationRegistry] = None,
) -> AgentApplicationRegistry:
    return registry or base_agent_application_registry()


def _record_by_id(
    application_id: str,
    registry: Optional[AgentApplicationRegistry] = None,
) -> AgentApplicationRecord:
    return _registry_or_base(registry).record_by_id(application_id)


def _profile_for_record(record: AgentApplicationRecord) -> AgentProfile:
    factory = record.profile_factory
    if not callable(factory):
        raise ValueError("Agent profile factory is not configured")
    return factory()


def _runtime_definition_for_profile(profile: AgentProfile) -> RuntimeDefinition:
    return RuntimeDefinition(
        agent_id=profile.profile_id,
        application_policy=ApplicationRuntimePolicy(
            default_mode=profile.default_mode,
            mode_tool_policy=AgentProfileToolPolicy(profile),
            write_path_policy=AgentProfileWritePathPolicy(profile),
            mode_runtime_policy=AgentProfileRuntimePolicy(profile),
        ),
    )


def _build_profile_application(
    record: AgentApplicationRecord,
    tools: Any,
) -> AgentApplication:
    manifest = record.to_manifest()
    profile = _profile_for_record(record)
    runtime_factory = record.runtime_factory
    definition = (
        runtime_factory() if callable(runtime_factory) else _runtime_definition_for_profile(profile)
    )
    extensions = list(definition.extensions or ())
    for extension in extensions:
        if hasattr(extension, "tools") and getattr(extension, "tools", None) is None:
            extension.tools = tools
    extension_manager = ExtensionManager(extensions)
    detectors_factory = record.workspace_profile_detectors_factory
    detectors = detectors_factory() if callable(detectors_factory) else ()
    return AgentApplication(
        application_id=manifest.application_id,
        label=manifest.label,
        profile=profile,
        extension_manager=extension_manager,
        manifest=manifest,
        runtime_definition=definition,
        workflow_refreshers=tuple(extensions),
        workspace_profile_detectors=tuple(detectors or ()),
    )


def generic_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(GENERIC_AGENT_APPLICATION_ID).to_manifest()


def python_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(PYTHON_AGENT_APPLICATION_ID).to_manifest()


def html_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(HTML_AGENT_APPLICATION_ID).to_manifest()


def available_agent_application_manifests(
    registry: Optional[AgentApplicationRegistry] = None,
) -> List[AgentApplicationManifest]:
    return _registry_or_base(registry).manifests()


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
        "runtime_requirements": list(
            getattr(manifest, "runtime_requirements", ()) or ()
        ),
        "distribution_id": str(raw.get("distribution_id") or ""),
        "registration_entry": str(raw.get("registration_entry") or ""),
    }


def agent_application_capability_payload(
    application_id: str = "",
    registry: Optional[AgentApplicationRegistry] = None,
) -> Dict[str, Any]:
    selected_registry = _registry_or_base(registry)
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
    return _build_profile_application(record, tools)
