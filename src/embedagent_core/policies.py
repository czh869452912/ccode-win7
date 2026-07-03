from __future__ import annotations

from typing import Any, List, Protocol


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
