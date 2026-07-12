from __future__ import annotations

from typing import Any, Dict, List

from embedagent_core.session import Observation
from embedagent_core.tool_contracts import ToolDefinition

from embedagent_host.runtime.self_extension_authoring import (
    AuthoringRequest,
    SelfExtensionAuthoringService,
)
from embedagent_host.runtime.tools._base import ToolContext


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:
    def _author_local_capability(arguments: Dict[str, Any]) -> Observation:
        result = SelfExtensionAuthoringService(ctx.workspace).author(
            AuthoringRequest(
                kind=str(arguments.get("kind") or ""),
                name=str(arguments.get("name") or ""),
                summary=str(arguments.get("summary") or ""),
                body=str(arguments.get("body") or ""),
                command=str(arguments.get("command") or ""),
                recipe_action=str(arguments.get("recipe_action") or "custom"),
                permissions=list(arguments.get("permissions") or ["read"]),
                overwrite=bool(arguments.get("overwrite", False)),
            )
        )
        return Observation(
            tool_name="author_local_capability",
            success=result.success,
            error=(
                None
                if result.success
                else "; ".join(str(item.get("error") or "") for item in result.diagnostics)
            ),
            data=result.to_dict(),
        )

    return [
        ToolDefinition(
            name="author_local_capability",
            description=(
                "Create local self-extension artifacts under .embedagent. "
                "This writes skills, prompts, recipes, or disabled project extension skeletons; "
                "it does not reload resources or load Python extensions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["skill", "prompt", "recipe", "extension"],
                    },
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "body": {"type": "string"},
                    "command": {"type": "string"},
                    "recipe_action": {"type": "string"},
                    "permissions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "overwrite": {"type": "boolean"},
                },
                "required": ["kind", "name"],
                "additionalProperties": False,
            },
            handler=_author_local_capability,
            read_only=False,
            concurrency_safe=False,
        )
    ]
