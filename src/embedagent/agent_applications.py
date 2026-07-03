from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent.agent_profiles import (
    AgentProfile,
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
class AgentApplicationDefinition:
    application_id: str
    manifest_loader: Callable[[], AgentApplicationManifest]
    builder: Callable[[Any], AgentApplication]


def _profile_application_manifest(
    application_id: str,
    label: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentApplicationManifest:
    return AgentApplicationManifest(
        application_id=application_id,
        label=label,
        profile_id=application_id,
        workflow_package_ids=(),
        source_type="builtin",
        source_id="embedagent.agent_profiles",
        default=False,
        metadata=dict(metadata or {}),
    )


def _build_profile_application(
    manifest: AgentApplicationManifest,
    profile: AgentProfile,
) -> AgentApplication:
    return AgentApplication(
        application_id=manifest.application_id,
        label=manifest.label,
        profile=profile,
        extension_manager=ExtensionManager(),
        manifest=manifest,
    )


def generic_agent_application_manifest() -> AgentApplicationManifest:
    return _profile_application_manifest(
        GENERIC_AGENT_APPLICATION_ID,
        "Generic Agent",
        {"domain": "generic"},
    )


def python_agent_application_manifest() -> AgentApplicationManifest:
    return _profile_application_manifest(
        PYTHON_AGENT_APPLICATION_ID,
        "Python Agent",
        {"domain": "python"},
    )


def html_agent_application_manifest() -> AgentApplicationManifest:
    return _profile_application_manifest(
        HTML_AGENT_APPLICATION_ID,
        "HTML Agent",
        {"domain": "html"},
    )


def _build_generic_agent_application(tools: Any) -> AgentApplication:
    del tools
    manifest = generic_agent_application_manifest()
    return _build_profile_application(manifest, generic_agent_profile())


def _build_python_agent_application(tools: Any) -> AgentApplication:
    del tools
    manifest = python_agent_application_manifest()
    return _build_profile_application(manifest, python_agent_profile())


def _build_html_agent_application(tools: Any) -> AgentApplication:
    del tools
    manifest = html_agent_application_manifest()
    return _build_profile_application(manifest, html_agent_profile())


def _c_cpp_agent_application_manifest() -> AgentApplicationManifest:
    from embedagent.workflow_packages.c_cpp.application import c_cpp_agent_application_manifest

    return c_cpp_agent_application_manifest()


def _build_c_cpp_agent_application(tools: Any) -> AgentApplication:
    from embedagent.workflow_packages.c_cpp.application import build_c_cpp_agent_application

    return build_c_cpp_agent_application(tools)


def _builtin_agent_application_definitions() -> Tuple[AgentApplicationDefinition, ...]:
    return (
        AgentApplicationDefinition(
            application_id=DEFAULT_AGENT_APPLICATION_ID,
            manifest_loader=_c_cpp_agent_application_manifest,
            builder=_build_c_cpp_agent_application,
        ),
        AgentApplicationDefinition(
            application_id=GENERIC_AGENT_APPLICATION_ID,
            manifest_loader=generic_agent_application_manifest,
            builder=_build_generic_agent_application,
        ),
        AgentApplicationDefinition(
            application_id=PYTHON_AGENT_APPLICATION_ID,
            manifest_loader=python_agent_application_manifest,
            builder=_build_python_agent_application,
        ),
        AgentApplicationDefinition(
            application_id=HTML_AGENT_APPLICATION_ID,
            manifest_loader=html_agent_application_manifest,
            builder=_build_html_agent_application,
        ),
    )


def available_agent_application_manifests() -> List[AgentApplicationManifest]:
    return [definition.manifest_loader() for definition in _builtin_agent_application_definitions()]


def build_agent_application(application_id: str, tools: Any) -> AgentApplication:
    requested = str(application_id or "").strip() or DEFAULT_AGENT_APPLICATION_ID
    for definition in _builtin_agent_application_definitions():
        if requested == definition.application_id:
            return definition.builder(tools)
    raise ValueError("Unknown agent application %r" % (application_id,))
