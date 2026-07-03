from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from embedagent_core.session import Observation


class ToolError(Exception):
    def __init__(
        self,
        message: str,
        error_kind: str = "tool_error",
        retryable: bool = True,
        outcome_class: str = "",
        suggested_next_step: str = "",
    ) -> None:
        super(ToolError, self).__init__(message)
        self.error_kind = str(error_kind or "tool_error")
        self.retryable = bool(retryable)
        self.outcome_class = str(outcome_class or "")
        self.suggested_next_step = str(suggested_next_step or "")

    def to_observation_data(self) -> Dict[str, Any]:
        data = {
            "error_kind": self.error_kind,
            "retryable": self.retryable,
        }
        if self.outcome_class:
            data["outcome_class"] = self.outcome_class
        if self.suggested_next_step:
            data["suggested_next_step"] = self.suggested_next_step
        return data


def diagnostic_tool_error(
    message: str, error_kind: str, suggested_next_step: str = ""
) -> ToolError:
    return ToolError(
        message,
        error_kind=error_kind,
        retryable=False,
        outcome_class="diagnostic_failure",
        suggested_next_step=suggested_next_step,
    )


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Observation]
    metadata: Dict[str, Any] = field(default_factory=dict)
    read_only: bool = False
    concurrency_safe: bool = False
    interrupt_behavior: str = "block"
    result_budget_policy: str = "default"
    activity_kind: str = "tool"
    context_priority: int = 50

    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolExecutionSpec:
    read_only: bool
    concurrency_safe: bool
    interrupt_behavior: str
    result_budget_policy: str


@dataclass
class ToolPresentation:
    user_label: str
    progress_renderer_key: str
    result_renderer_key: str
    supports_diff_preview: bool


@dataclass
class ToolContextPolicy:
    context_reducer_key: str
    activity_kind: str
    context_priority: int
    read_model_invalidations: List[str]


@dataclass
class ToolCatalogEntry:
    name: str
    description: str
    permission_category: str
    mode_visibility: List[str]
    workflow_visibility: List[str]
    execution: ToolExecutionSpec
    presentation: ToolPresentation
    context_policy: ToolContextPolicy
    source_type: str
    source_id: str

    @property
    def user_label(self) -> str:
        return self.presentation.user_label

    @property
    def progress_renderer_key(self) -> str:
        return self.presentation.progress_renderer_key

    @property
    def result_renderer_key(self) -> str:
        return self.presentation.result_renderer_key

    @property
    def supports_diff_preview(self) -> bool:
        return self.presentation.supports_diff_preview

    @property
    def context_reducer_key(self) -> str:
        return self.context_policy.context_reducer_key

    @property
    def read_only(self) -> bool:
        return self.execution.read_only

    @property
    def concurrency_safe(self) -> bool:
        return self.execution.concurrency_safe

    @property
    def interrupt_behavior(self) -> str:
        return self.execution.interrupt_behavior

    @property
    def result_budget_policy(self) -> str:
        return self.execution.result_budget_policy

    @property
    def activity_kind(self) -> str:
        return self.context_policy.activity_kind

    @property
    def context_priority(self) -> int:
        return self.context_policy.context_priority

    @property
    def read_model_invalidations(self) -> List[str]:
        return list(self.context_policy.read_model_invalidations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permission_category": self.permission_category,
            "mode_visibility": list(self.mode_visibility),
            "workflow_visibility": list(self.workflow_visibility),
            "user_label": self.user_label,
            "progress_renderer_key": self.progress_renderer_key,
            "result_renderer_key": self.result_renderer_key,
            "supports_diff_preview": self.supports_diff_preview,
            "context_reducer_key": self.context_reducer_key,
            "read_only": self.read_only,
            "concurrency_safe": self.concurrency_safe,
            "interrupt_behavior": self.interrupt_behavior,
            "result_budget_policy": self.result_budget_policy,
            "activity_kind": self.activity_kind,
            "context_priority": self.context_priority,
            "read_model_invalidations": self.read_model_invalidations,
            "source_type": self.source_type,
            "source_id": self.source_id,
        }


class WorkspacePathResolver(Protocol):
    def resolve_path(self, path: str, allow_missing: bool = False) -> str:
        raise NotImplementedError


class ToolRuntimePort(Protocol):
    workspace: str
    tool_result_store: Any
    projection_db: Any

    def schemas_for(
        self,
        mode: str,
        workflow_state: Optional[Dict[str, Any]] = None,
        tool_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def execute_with_interrupt(
        self,
        name: str,
        arguments: Dict[str, Any],
        stop_event: Any,
    ) -> Observation:
        raise NotImplementedError

    def catalog_entry(self, tool_name: str) -> Optional[ToolCatalogEntry]:
        raise NotImplementedError

    def path_resolver(self) -> WorkspacePathResolver:
        raise NotImplementedError
