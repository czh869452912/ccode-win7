from __future__ import annotations

from embedagent.harness.runner import HarnessRunner
from embedagent.modes import allowed_tools_for
from embedagent.tools_v2.runtime import ToolRuntimeV2


class HarnessToolBridge(object):
    def __init__(self, legacy_runtime, harness_runner=None):
        self.legacy_runtime = legacy_runtime
        self.harness_runner = harness_runner or HarnessRunner()
        self.harness_runtime = ToolRuntimeV2(
            legacy_runtime.workspace,
            app_config=getattr(legacy_runtime, "app_config", None),
        )

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
        if context is not None:
            return set(self.harness_runtime.schemas_for_pack(context.pack_name, names_only=True)) | set(allowed_tools_for(mode_name))
        return set(allowed_tools_for(mode_name))

    def schemas_for_mode(self, mode_name, workflow_state="chat"):
        context = self.describe_mode(mode_name, workflow_state=workflow_state)
        if context is not None:
            return self.harness_runtime.schemas_for_pack(context.pack_name)
        runtime_schemas = getattr(self.legacy_runtime, "schemas_for", None)
        if callable(runtime_schemas):
            return runtime_schemas(
                mode_name,
                workflow_state=workflow_state,
                tool_names=list(allowed_tools_for(mode_name)),
            )
        schemas = []
        for item in self.legacy_runtime.schemas():
            name = item.get("function", {}).get("name", "")
            if name in allowed_tools_for(mode_name):
                schemas.append(item)
        return schemas

    def tool_capabilities(self, mode_name, tool_name, workflow_state="chat"):
        context = self.describe_mode(mode_name, workflow_state=workflow_state)
        if context is not None and self.harness_runtime.has_tool(tool_name):
            return self.harness_runtime.tool_capabilities(tool_name)
        lookup = getattr(self.legacy_runtime, "tool_capabilities", None)
        if callable(lookup):
            return lookup(tool_name)
        return {}

    def execute_with_interrupt(self, mode_name, tool_name, arguments, stop_event=None, workflow_state="chat"):
        context = self.describe_mode(mode_name, workflow_state=workflow_state)
        if context is not None and self.harness_runtime.has_tool(tool_name):
            return self.harness_runtime.execute_with_interrupt(tool_name, arguments, stop_event)
        return self.legacy_runtime.execute_with_interrupt(tool_name, arguments, stop_event)

    def execute(self, mode_name, tool_name, arguments, workflow_state="chat"):
        return self.execute_with_interrupt(
            mode_name,
            tool_name,
            arguments,
            stop_event=None,
            workflow_state=workflow_state,
        )
