from __future__ import annotations

C_WORKFLOW_CORE_PACK = [
    "read_file",
    "list_dir",
    "grep_text",
    "edit_file",
    "write_file",
    "ask_user",
]

C_WORKFLOW_BUILD_LITE_PACK = C_WORKFLOW_CORE_PACK + [
    "glob_files",
    "list_compilers",
    "configure_build_env",
    "run_build",
    "list_recipes",
    "run_recipe",
    "task_status",
]

C_WORKFLOW_DEBUG_LITE_PACK = [
    "read_file",
    "list_dir",
    "grep_text",
    "edit_file",
    "write_file",
    "list_compilers",
    "configure_build_env",
    "run_build",
    "run_recipe",
    "ask_user",
    "task_status",
    "glob_files",
    "list_recipes",
    "record_failing_evidence",
]

C_WORKFLOW_VERIFY_PACK = [
    "list_compilers",
    "run_build",
    "list_recipes",
    "run_recipe",
    "report_quality_v2",
    "task_status",
    "ask_user",
]

C_WORKFLOW_PACKS = {
    "core": C_WORKFLOW_CORE_PACK,
    "build_lite": C_WORKFLOW_BUILD_LITE_PACK,
    "debug_lite": C_WORKFLOW_DEBUG_LITE_PACK,
    "verify": C_WORKFLOW_VERIFY_PACK,
}


def pack_tool_names(pack_name):
    return list(C_WORKFLOW_PACKS.get(str(pack_name or "core"), C_WORKFLOW_CORE_PACK))
