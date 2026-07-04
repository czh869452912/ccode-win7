from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from embedagent.agent_profiles import (
    AgentProfile,
    default_c_cpp_agent_profile,
    generic_agent_profile,
    html_agent_profile,
    python_agent_profile,
)
from embedagent_core.extensions import ExtensionManager

DEFAULT_AGENT_APPLICATION_ID = "embedagent.default_c_cpp"
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
    workflow_refreshers: Tuple[Any, ...] = field(default_factory=tuple)

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
    profile_kind: str
    workflow_package_ids: Tuple[str, ...] = field(default_factory=tuple)
    workflow_kind: str = ""
    source_type: str = "builtin"
    source_id: str = ""
    default: bool = False
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


BUILTIN_AGENT_APPLICATION_RECORDS = (
    AgentApplicationRecord(
        application_id=DEFAULT_AGENT_APPLICATION_ID,
        label="Default C/C++ Agent",
        profile_id=DEFAULT_AGENT_APPLICATION_ID,
        profile_kind="default_c_cpp",
        workflow_package_ids=("embedagent.c_workflow",),
        workflow_kind="c_cpp",
        source_type="builtin",
        source_id="embedagent.workflow_packages.c_cpp",
        default=True,
    ),
    AgentApplicationRecord(
        application_id=GENERIC_AGENT_APPLICATION_ID,
        label="Generic Agent",
        profile_id=GENERIC_AGENT_APPLICATION_ID,
        profile_kind="generic",
        source_type="builtin",
        source_id="embedagent.agent_profiles",
        metadata={"domain": "generic"},
    ),
    AgentApplicationRecord(
        application_id=PYTHON_AGENT_APPLICATION_ID,
        label="Python Agent",
        profile_id=PYTHON_AGENT_APPLICATION_ID,
        profile_kind="python",
        source_type="builtin",
        source_id="embedagent.agent_profiles",
        metadata={"domain": "python"},
    ),
    AgentApplicationRecord(
        application_id=HTML_AGENT_APPLICATION_ID,
        label="HTML Agent",
        profile_id=HTML_AGENT_APPLICATION_ID,
        profile_kind="html",
        source_type="builtin",
        source_id="embedagent.agent_profiles",
        metadata={"domain": "html"},
    ),
)


def _record_by_id(application_id: str) -> AgentApplicationRecord:
    requested = str(application_id or "").strip() or DEFAULT_AGENT_APPLICATION_ID
    for record in BUILTIN_AGENT_APPLICATION_RECORDS:
        if requested == record.application_id:
            return record
    raise ValueError("Unknown agent application %r" % (application_id,))


def _profile_for_record(record: AgentApplicationRecord) -> AgentProfile:
    if record.profile_kind == "default_c_cpp":
        return default_c_cpp_agent_profile()
    if record.profile_kind == "generic":
        return generic_agent_profile()
    if record.profile_kind == "python":
        return python_agent_profile()
    if record.profile_kind == "html":
        return html_agent_profile()
    raise ValueError("Unknown agent profile kind %r" % (record.profile_kind,))


def _build_profile_application(
    record: AgentApplicationRecord,
    profile: AgentProfile,
) -> AgentApplication:
    manifest = record.to_manifest()
    return AgentApplication(
        application_id=manifest.application_id,
        label=manifest.label,
        profile=profile,
        extension_manager=ExtensionManager(),
        manifest=manifest,
    )


def generic_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(GENERIC_AGENT_APPLICATION_ID).to_manifest()


def python_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(PYTHON_AGENT_APPLICATION_ID).to_manifest()


def html_agent_application_manifest() -> AgentApplicationManifest:
    return _record_by_id(HTML_AGENT_APPLICATION_ID).to_manifest()


def available_agent_application_manifests() -> List[AgentApplicationManifest]:
    return [record.to_manifest() for record in BUILTIN_AGENT_APPLICATION_RECORDS]


def build_agent_application(application_id: str, tools: Any) -> AgentApplication:
    record = _record_by_id(application_id)
    if record.workflow_kind == "c_cpp":
        from embedagent.workflow_packages.c_cpp.application import build_c_cpp_agent_application

        return build_c_cpp_agent_application(tools)
    if record.workflow_kind:
        raise ValueError("Unknown workflow kind %r" % (record.workflow_kind,))
    return _build_profile_application(record, _profile_for_record(record))
