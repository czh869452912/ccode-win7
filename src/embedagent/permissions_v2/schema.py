from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PermissionRuleV1:
    tool: str
    decision: str
    path: str = ""
    recipe: str = ""
    command_prefix: str = ""
