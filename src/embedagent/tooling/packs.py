from __future__ import annotations


CORE_PACK = [
    "read_file",
    "list_dir",
    "grep_text",
    "edit_file",
    "write_file",
    "run_recipe",
    "ask_user",
    "task_status",
]


BUILD_LITE_PACK = CORE_PACK + [
    "glob_files",
    "list_recipes",
]


PACKS = {
    "core": CORE_PACK,
    "build_lite": BUILD_LITE_PACK,
}


def pack_tool_names(pack_name):
    return list(PACKS.get(str(pack_name or "core"), CORE_PACK))
