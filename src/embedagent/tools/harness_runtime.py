from __future__ import annotations

from typing import Dict, List

from embedagent.harness.runner import HarnessRunner
from embedagent.modes import allowed_tools_for
from embedagent.tooling.packs import pack_tool_names
from embedagent.tools import discovery_ops, recipe_ops, session_ops


OFFICIAL_HARNESS_TOOL_METADATA = {
    "list_dir": {
        "permission_category": "read",
        "mode_visibility": ["build", "debug", "explore", "spec"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "List Dir",
        "progress_renderer_key": "list",
        "result_renderer_key": "list",
        "supports_diff_preview": False,
        "context_reducer_key": "list_dir",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "list",
        "context_priority": 72,
    },
    "glob_files": {
        "permission_category": "read",
        "mode_visibility": ["build", "debug", "explore", "spec"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Glob Files",
        "progress_renderer_key": "search",
        "result_renderer_key": "search",
        "supports_diff_preview": False,
        "context_reducer_key": "glob_files",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "search",
        "context_priority": 78,
    },
    "grep_text": {
        "permission_category": "read",
        "mode_visibility": ["build", "debug", "explore", "spec"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Grep Text",
        "progress_renderer_key": "search",
        "result_renderer_key": "search",
        "supports_diff_preview": False,
        "context_reducer_key": "grep_text",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "search",
        "context_priority": 86,
    },
    "list_recipes": {
        "permission_category": "read",
        "mode_visibility": ["build", "debug", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "List Recipes",
        "progress_renderer_key": "recipe",
        "result_renderer_key": "recipe",
        "supports_diff_preview": False,
        "context_reducer_key": "list_recipes",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "recipe",
        "context_priority": 70,
    },
    "run_recipe": {
        "permission_category": "toolchain_exec",
        "mode_visibility": ["build", "debug", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Run Recipe",
        "progress_renderer_key": "toolchain",
        "result_renderer_key": "toolchain",
        "supports_diff_preview": False,
        "context_reducer_key": "run_recipe",
        "read_only": False,
        "concurrency_safe": False,
        "interrupt_behavior": "cancel",
        "result_budget_policy": "artifact-first",
        "activity_kind": "diagnostic",
        "context_priority": 100,
    },
    "report_quality_v2": {
        "permission_category": "read",
        "mode_visibility": ["verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Quality Report V2",
        "progress_renderer_key": "quality",
        "result_renderer_key": "quality",
        "supports_diff_preview": False,
        "context_reducer_key": "report_quality_v2",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "diagnostic",
        "context_priority": 88,
    },
    "task_status": {
        "permission_category": "read",
        "mode_visibility": ["build", "debug", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Task Status",
        "progress_renderer_key": "todos",
        "result_renderer_key": "todos",
        "supports_diff_preview": False,
        "context_reducer_key": "task_status",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "todo",
        "context_priority": 98,
    },
    "ask_user": {
        "permission_category": "read",
        "mode_visibility": ["explore", "spec", "build", "debug", "verify"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Ask User",
        "progress_renderer_key": "interaction",
        "result_renderer_key": "interaction",
        "supports_diff_preview": False,
        "context_reducer_key": "ask_user",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "interaction",
        "context_priority": 99,
    },
    "record_failing_evidence": {
        "permission_category": "read",
        "mode_visibility": ["debug"],
        "workflow_visibility": ["chat", "plan", "review", "command"],
        "user_label": "Record Failing Evidence",
        "progress_renderer_key": "default",
        "result_renderer_key": "default",
        "supports_diff_preview": False,
        "context_reducer_key": "record_failing_evidence",
        "read_only": True,
        "concurrency_safe": True,
        "interrupt_behavior": "block",
        "result_budget_policy": "compact-preview",
        "activity_kind": "diagnostic",
        "context_priority": 82,
    },
}


def build_harness_tools(ctx) -> List[object]:
    definitions = []
    definitions.extend(discovery_ops.build_tools(ctx))
    definitions.extend(recipe_ops.build_tools(ctx))
    definitions.extend(session_ops.build_tools(ctx))
    return definitions


class OfficialRuntimeModes(object):
    def __init__(self, harness_runner=None):
        self.harness_runner = harness_runner or HarnessRunner()

    def describe_mode(self, mode_name, workflow_state="chat", current_phase="", observations=None):
        discipline_override = None
        if str(mode_name or "") == "build" and str(workflow_state or "") == "plan":
            discipline_override = "full_spec_tdd"
        return self.harness_runner.describe_mode(
            mode_name,
            discipline_override=discipline_override,
            current_phase=current_phase,
            observations=observations,
        )

    def allowed_tool_names(self, mode_name, workflow_state="chat"):
        context = self.describe_mode(mode_name, workflow_state=workflow_state)
        if context is None:
            return set(allowed_tools_for(mode_name))
        return set(pack_tool_names(context.pack_name)) | set(allowed_tools_for(mode_name))

    def pack_tool_names_for_mode(self, mode_name, workflow_state="chat"):
        context = self.describe_mode(mode_name, workflow_state=workflow_state)
        if context is None:
            return []
        return list(pack_tool_names(context.pack_name))
