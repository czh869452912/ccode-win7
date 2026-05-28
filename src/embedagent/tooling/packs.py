from __future__ import annotations

# Base tool vocabulary shared by harness build-class packs.
# It is workflow-neutral in the sense that it has no recipe/task harness tools.
# Non-harness modes such as explore/spec are not in the harness registry and do
# not receive this pack.
CORE_PACK = [
    "read_file",
    "list_dir",
    "grep_text",
    "edit_file",
    "write_file",
    "ask_user",
]


BUILD_LITE_PACK = CORE_PACK + [
    "glob_files",
    "list_recipes",
    "run_recipe",
    "task_status",
]


DEBUG_LITE_PACK = [
    "read_file",
    "list_dir",
    "grep_text",
    "edit_file",
    "write_file",
    "run_recipe",
    "ask_user",
    "task_status",
    "glob_files",
    "list_recipes",
    "record_failing_evidence",
]


VERIFY_PACK = [
    "list_recipes",
    "run_recipe",
    "report_quality_v2",
    "task_status",
    "ask_user",
]


PACKS = {
    "core": CORE_PACK,
    "build_lite": BUILD_LITE_PACK,
    "debug_lite": DEBUG_LITE_PACK,
    "verify": VERIFY_PACK,
}


def pack_tool_names(pack_name):
    return list(PACKS.get(str(pack_name or "core"), CORE_PACK))
