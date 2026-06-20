from __future__ import annotations

from typing import Any, Dict


def register_c_workflow_context_reducers(reducer_registry: Any) -> None:
    reducer_registry.register_reducer("list_recipes", reducer_registry._reduce_list)
    reducer_registry.register_reducer("list_compilers", reducer_registry._reduce_list)
    reducer_registry.register_reducer("configure_build_env", reducer_registry._reduce_generic)
    reducer_registry.register_reducer(
        "run_build",
        lambda data, detailed, policy: reduce_diagnostics_tool(
            data, detailed, policy, reducer_registry
        ),
    )
    reducer_registry.register_reducer(
        "run_recipe",
        lambda data, detailed, policy: reduce_recipe_result(
            data, detailed, policy, reducer_registry
        ),
    )
    reducer_registry.register_reducer(
        "report_quality_v2",
        lambda data, detailed, policy: reduce_quality(data, detailed, policy, reducer_registry),
    )
    reducer_registry.register_reducer(
        "task_status",
        lambda data, detailed, policy: reduce_tasks(data, detailed, policy, reducer_registry),
    )
    reducer_registry.register_reducer(
        "record_failing_evidence",
        reducer_registry._reduce_generic,
    )
    reducer_registry.register_high_priority_tool("run_build")
    reducer_registry.register_high_priority_tool("run_recipe")
    reducer_registry.register_high_priority_tool("report_quality_v2")


def reduce_diagnostics_tool(
    data: Dict[str, Any],
    detailed: bool,
    policy: Any,
    helpers: Any,
) -> Dict[str, Any]:
    result = helpers._reduce_command(data, detailed, policy)
    result.update(
        helpers._copy(
            data,
            "error_count",
            "warning_count",
            "note_count",
            "diagnostic_count",
            "diagnostics_stored_path",
            "diagnostics_item_count",
        )
    )
    result["diagnostics"] = helpers._diagnostics(data.get("diagnostics") or [], detailed)
    return result


def reduce_recipe_result(
    data: Dict[str, Any],
    detailed: bool,
    policy: Any,
    helpers: Any,
) -> Dict[str, Any]:
    result = reduce_diagnostics_tool(data, detailed, policy, helpers)
    result.update(
        helpers._copy(
            data,
            "recipe_id",
            "recipe_label",
            "recipe_source",
            "recipe_action",
            "family",
            "stage",
            "target",
            "profile",
        )
    )
    if isinstance(data.get("test_summary"), dict):
        summary = helpers._copy(data["test_summary"], "total", "passed", "failed", "skipped")
        summary["failures"] = helpers._simple_list(
            data["test_summary"].get("failures") or [], 5 if detailed else 3
        )
        result["test_summary"] = summary
    if isinstance(data.get("coverage_summary"), dict):
        result["coverage_summary"] = helpers._copy(
            data["coverage_summary"],
            "line_coverage",
            "region_coverage",
            "function_coverage",
            "lines_covered",
            "lines_total",
            "functions_covered",
            "functions_total",
            "regions_covered",
            "regions_total",
        )
    return result


def reduce_quality(
    data: Dict[str, Any],
    detailed: bool,
    policy: Any,
    helpers: Any,
) -> Dict[str, Any]:
    result = helpers._copy(
        data,
        "passed",
        "error_count",
        "warning_count",
        "test_failures",
        "line_coverage",
        "min_line_coverage",
    )
    result["reasons"] = helpers._simple_list(data.get("reasons") or [], 6 if detailed else 3)
    return result


def reduce_tasks(
    data: Dict[str, Any],
    detailed: bool,
    policy: Any,
    helpers: Any,
) -> Dict[str, Any]:
    result = helpers._copy(
        data,
        "action",
        "count",
        "id",
        "content",
        "removed_id",
        "remaining",
        "summary",
        "failing_evidence_ready",
        "returned_count",
        "total_count",
        "has_more",
        "next_offset",
        "result_ref",
    )
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        limit = 12 if detailed else 6
        result["tasks"] = helpers._simple_list(tasks, limit)
    preview = data.get("preview")
    if isinstance(preview, list):
        result["preview"] = helpers._simple_list(preview, 12 if detailed else 6)
    return result
