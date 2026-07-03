from __future__ import annotations

from typing import Any, Dict, List, Protocol, Tuple


class ModeToolPolicy(Protocol):
    def allowed_tools_for(self, mode_name: str, workflow_state: Any = None) -> List[str]:
        raise NotImplementedError


class WritePathPolicy(Protocol):
    def is_path_writable(
        self,
        mode_name: str,
        normalized_path: str,
        app_config: Any = None,
    ) -> bool:
        raise NotImplementedError


class ModeRuntimePolicy(Protocol):
    def default_mode(self) -> str:
        raise NotImplementedError

    def require_mode(self, mode_name: str) -> Dict[str, Any]:
        raise NotImplementedError

    def build_system_prompt(
        self,
        mode_name: str,
        app_config: Any = None,
        workspace: str = "",
        local_resources: Any = None,
    ) -> str:
        raise NotImplementedError

    def parse_mode_switch_request(
        self,
        user_text: str,
        fallback_mode: str,
    ) -> Tuple[str, str, bool]:
        raise NotImplementedError


class EmptyModeToolPolicy(object):
    def allowed_tools_for(self, mode_name: str, workflow_state: Any = None) -> List[str]:
        del mode_name, workflow_state
        return []


class DenyWritePathPolicy(object):
    def is_path_writable(
        self,
        mode_name: str,
        normalized_path: str,
        app_config: Any = None,
    ) -> bool:
        del mode_name, normalized_path, app_config
        return False


class PassThroughModeRuntimePolicy(object):
    def __init__(self, default_mode_name: str = "explore") -> None:
        self._default_mode_name = str(default_mode_name or "explore")

    def default_mode(self) -> str:
        return self._default_mode_name

    def require_mode(self, mode_name: str) -> Dict[str, Any]:
        slug = str(mode_name or self._default_mode_name)
        return {"slug": slug}

    def build_system_prompt(
        self,
        mode_name: str,
        app_config: Any = None,
        workspace: str = "",
        local_resources: Any = None,
    ) -> str:
        del app_config, workspace, local_resources
        return "Current mode: %s" % str(mode_name or self._default_mode_name)

    def parse_mode_switch_request(
        self,
        user_text: str,
        fallback_mode: str,
    ) -> Tuple[str, str, bool]:
        return str(fallback_mode or self._default_mode_name), str(user_text or ""), False
