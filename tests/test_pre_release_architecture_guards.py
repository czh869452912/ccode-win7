from __future__ import unicode_literals

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = (".py", ".js", ".jsx")

ACTIVE_SOURCE_FILES = [
    ROOT / "src/embedagent/protocol/__init__.py",
    ROOT / "src/embedagent/session_projector.py",
    ROOT / "src/embedagent/core/adapter.py",
    ROOT / "src/embedagent_host/inprocess_adapter.py",
    ROOT / "src/embedagent/frontend/gui/backend/server.py",
    ROOT / "src/embedagent/frontend/gui/webapp/src/state-helpers.js",
    ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx",
    ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js",
    ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js",
]


def _read(path):
    return path.read_text(encoding="utf-8")


def _relative(path):
    return path.relative_to(ROOT).as_posix()


def _source_files_under(*relative_roots, **kwargs):
    suffixes = kwargs.get("suffixes", SOURCE_SUFFIXES)
    files = []
    for relative_root in relative_roots:
        root = ROOT / relative_root
        if root.is_file():
            candidates = [root]
        else:
            candidates = list(root.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            rel = _relative(path)
            if "__pycache__" in path.parts:
                continue
            if "/frontend/gui/static/" in rel:
                continue
            if path.suffix in suffixes:
                files.append(path)
    return files


def test_no_timeline_replay_snapshot_contract_in_active_source():
    forbidden = (
        "timeline" + "_replay_status",
        "timeline" + "_first_seq",
        "timeline" + "_last_seq",
        "timeline" + "_integrity",
    )
    offenders = []
    for path in ACTIVE_SOURCE_FILES:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []


def test_no_session_timeline_api_in_active_source():
    files = [
        ROOT / "src/embedagent/protocol/__init__.py",
        ROOT / "src/embedagent/core/adapter.py",
        ROOT / "src/embedagent_host/inprocess_adapter.py",
        ROOT / "src/embedagent/frontend/tui/services/timeline.py",
    ]
    offenders = []
    for path in files:
        text = _read(path)
        if "get_session" + "_timeline" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_no_core_flat_timeline_builder_name():
    text = _read(ROOT / "src/embedagent/session_history.py")
    assert "build_flat" + "_timeline" not in text


def test_no_tui_flat_or_event_history_projection_contract():
    files = [
        ROOT / "src/embedagent/session_history.py",
        ROOT / "src/embedagent/frontend/tui/controller.py",
        ROOT / "src/embedagent/frontend/tui/frontend_adapter.py",
        ROOT / "src/embedagent/frontend/tui/services/timeline.py",
        ROOT / "src/embedagent/frontend/tui/views/timeline.py",
        ROOT / "src/embedagent/frontend/tui/views/__init__.py",
    ]
    forbidden = [
        "build_flat" + "_history",
        "Flat" + "TimelineView",
        "flat" + "_timeline",
        "get" + "_timeline_data",
        "update" + "_flat_timeline",
        "handle" + "_item_updated",
        "handle" + "_item_completed",
        "format" + "_timeline_records",
        'payload.get("events")',
        '"items": []',
    ]
    offenders = []
    for path in files:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []


def test_no_flat_timeline_view_or_builder_paths():
    forbidden = (
        "Flat" + "TimelineView",
        "build_flat" + "_history",
        "build_flat" + "_timeline",
        "timeline" + "FromTurns",
        "timeline" + "FromEvents",
    )
    forbidden_paths = ("src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js",)
    offenders = []
    for path in _source_files_under(
        "src/embedagent",
        "src/embedagent_core",
        "src/embedagent_host",
    ):
        text = _read(path)
        rel = _relative(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    for rel_path in forbidden_paths:
        if (ROOT / rel_path).exists():
            offenders.append("%s exists" % rel_path)
    assert offenders == []


def test_no_session_view_clear_uses_timeline_payload():
    files = [
        ROOT / "src/embedagent_host/inprocess_adapter.py",
        ROOT / "src/embedagent/frontend/gui/webapp/src/store.js",
    ]
    offenders = []
    for path in files:
        text = _read(path)
        if "clear" + "_timeline" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_cli_shell_does_not_construct_hosted_runtime_dependencies():
    text = _read(ROOT / "src/embedagent/cli.py")
    blocked = (
        "OpenAICompatibleClient(",
        "ToolRuntime(",
        "ContextManager(",
        "PermissionPolicy(",
        "InProcessAdapter(",
    )
    for needle in blocked:
        assert needle not in text


def test_active_prompt_sources_do_not_present_code_as_mode():
    files = [
        ROOT / "src/embedagent/modes.py",
        ROOT / "src/embedagent/workspace_profile.py",
    ]
    forbidden = (
        "code/debug",
        "code 模式",
        "/mode code",
    )
    offenders = []
    for path in files:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []


def test_tui_shell_does_not_construct_hosted_runtime_dependencies():
    for rel in (
        "src/embedagent/frontend/tui/launcher.py",
        "src/embedagent/frontend/tui/bootstrap.py",
    ):
        text = _read(ROOT / rel)
        blocked = (
            "OpenAICompatibleClient(",
            "ToolRuntime(",
            "ContextManager(",
            "PermissionPolicy(",
            "InProcessAdapter(",
            "load_config(",
        )
        for needle in blocked:
            assert needle not in text


def test_gui_shell_does_not_construct_hosted_runtime_dependencies():
    text = _read(ROOT / "src/embedagent/frontend/gui/launcher.py")
    blocked = (
        "OpenAICompatibleClient(",
        "ToolRuntime(",
        "ContextManager(",
        "PermissionPolicy(",
        "load_config(",
    )
    for needle in blocked:
        assert needle not in text


def test_gui_session_runtime_projector_is_removed():
    assert not (
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js"
    ).exists()


def test_gui_backend_routes_do_not_use_active_core_proxy():
    text = _read(ROOT / "src/embedagent/frontend/gui/backend/server.py")
    assert "_ActiveCoreProxy" not in text
    assert "self.core" not in text


def test_no_timeline_reload_route_or_metadata_in_active_gui_backend():
    files = [
        ROOT / "src/embedagent/frontend/gui/backend/server.py",
        ROOT / "src/embedagent/frontend/gui/backend/session_events.py",
        ROOT / "src/embedagent_host/inprocess_adapter.py",
        ROOT / "src/embedagent/core/adapter.py",
    ]
    offenders = []
    for path in files:
        text = _read(path)
        for token in (
            "/api/sessions/{session_id}/events",
            "_timeline_event",
            "load_session" + "_events_after",
        ):
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []


def test_no_legacy_task_tool_execution_contract_in_tests():
    legacy_tool = "manage" + "_to" + "dos"
    offenders = []
    for path in (ROOT / "tests").glob("test_*.py"):
        text = _read(path)
        forbidden = (
            'execute("%s"' % legacy_tool,
            "execute('%s'" % legacy_tool,
            '"tool_name", "%s"' % legacy_tool,
            "'tool_name', '%s'" % legacy_tool,
        )
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))
    assert offenders == []


def test_gui_backend_server_keeps_route_registration_delegated():
    text = _read(ROOT / "src/embedagent/frontend/gui/backend/server.py")
    route_decorator_count = (
        text.count("@app.get(") + text.count("@app.post(") + text.count("@app.delete(")
    )
    assert route_decorator_count <= 2
    for helper in (
        "register_app_routes(",
        "register_session_routes(",
        "register_terminal_routes(",
        "register_source_control_routes(",
        "register_preview_routes(",
    ):
        assert helper in text


def test_gui_backend_route_modules_do_not_import_server_helpers():
    offenders = []
    for path in sorted((ROOT / "src/embedagent/frontend/gui/backend").glob("routes_*.py")):
        text = _read(path)
        if "from embedagent.frontend.gui.backend.server import" in text:
            offenders.append(_relative(path))
    assert offenders == []

    server_text = _read(ROOT / "src/embedagent/frontend/gui/backend/server.py")
    forbidden_defs = (
        "def _serialize_session_snapshot",
        "def _serialize_session_summary",
        "def _serialize_interaction_response",
        "def _serialize_plan_snapshot",
        "def _serialize_permission_context",
        "def _thread_lifecycle_http_error",
        "def _terminal_http_error",
        "def _source_control_http_error",
        "def _preview_http_error",
    )
    leaked_helpers = [name for name in forbidden_defs if name in server_text]
    assert leaked_helpers == []


def test_session_snapshot_contract_uses_single_pending_interaction_payload():
    checked_files = {
        ROOT
        / "src/embedagent/protocol/__init__.py": (
            "has_pending_permission:",
            "has_pending_input:",
            "pending_permission: Optional",
            "pending_input: Optional",
        ),
        ROOT
        / "src/embedagent/session_projector.py": (
            '"has_pending_permission"',
            '"pending_permission"',
            '"has_pending_user_input"',
            '"pending_user_input"',
        ),
        ROOT
        / "src/embedagent/core/adapter.py": (
            "def _permission_request_from_snapshot",
            "def _user_input_request_from_snapshot",
            '"has_pending_user_input"',
            '"has_pending_input"',
            '"pending_permission"',
            '"pending_user_input"',
            '"pending_input"',
        ),
        ROOT
        / "src/embedagent/frontend/gui/backend/protocol_payloads.py": (
            '"has_pending_permission"',
            '"has_pending_input"',
            '"pending_permission"',
            '"pending_user_input"',
            '"pending_input"',
        ),
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/state-helpers.js": (
            "has_pending_permission",
            "has_pending_input",
            "pending_permission",
            "pending_user_input",
        ),
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/store.js": (
            "has_pending_permission",
            "has_pending_input",
            "pending_permission",
            "pending_user_input",
        ),
        ROOT
        / "docs/frontend-protocol.md": (
            "`has_pending_permission`",
            "`pending_permission`",
            "`has_pending_input`",
            "`pending_input`",
            "`pending_user_input`",
        ),
        ROOT
        / "tests/test_inprocess_adapter_frontend_api.py": (
            'restored["has_pending_permission"]',
            'resolved["has_pending_permission"]',
            '(waiting.get("pending_permission")',
            '"has_pending_permission": False',
        ),
    }
    offenders = []
    for path, tokens in checked_files.items():
        text = _read(path)
        for token in tokens:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []


def test_hosted_runtime_uses_single_pending_interaction_state():
    files = [
        ROOT / "src/embedagent/session_runtime.py",
        ROOT / "src/embedagent_host/hosted_interaction_service.py",
        ROOT / "src/embedagent_host/inprocess_adapter.py",
        ROOT / "src/embedagent/core/adapter.py",
        ROOT / "src/embedagent/session_projector.py",
        ROOT / "src/embedagent_host/hosted_command_service.py",
        ROOT / "src/embedagent/frontend/gui/backend/server.py",
        ROOT / "src/embedagent/services/session_lifecycle.py",
    ]
    forbidden = (
        "state.pending_permission",
        "state.pending_user_input",
        "state.pending_result",
        "state.pending_user_event",
        "state.pending_user_response",
        "pending_permission: Optional",
        "pending_user_input: Optional",
        "pending_result: Optional",
        "pending_user_event: Optional",
        "pending_user_response: Optional",
        "clear_pending_permission(",
        "clear_pending_user_input(",
        "_pending_permissions",
        "_pending_permission_results",
        "_pending_inputs",
        "_pending_input_results",
    )
    offenders = []
    for path in files:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []


def test_product_interfaces_expose_only_unified_interaction_response():
    files = [
        ROOT / "src/embedagent/core/adapter.py",
        ROOT / "src/embedagent/protocol/__init__.py",
        ROOT / "src/embedagent_host/inprocess_adapter.py",
        ROOT / "src/embedagent_host/hosted_interaction_service.py",
        ROOT / "src/embedagent/frontend/tui/services/sessions.py",
    ]
    forbidden = (
        "def approve_permission",
        "def reject_permission",
        "def reply_user_input",
        ".approve_permission(",
        ".reject_permission(",
        ".reply_user_input(",
    )
    offenders = []
    for path in files:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []


def test_shell_interaction_payloads_use_decision_and_answers_contract():
    files = [
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js",
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/composer/ComposerInteractionPanel.jsx",
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js",
        ROOT / "src/embedagent/frontend/tui/controller.py",
    ]
    forbidden = (
        "response_kind",
        "remember:",
        "selected_mode",
        "selected_option_text",
    )
    offenders = []
    for path in files:
        if not path.exists():
            continue
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []

    interaction_model = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js"
    )
    permission_builder = re.search(
        r"function buildPermissionResponse[\s\S]*?}\n",
        interaction_model,
    ) or re.search(
        r"export function buildPermissionResponse[\s\S]*?}\n",
        interaction_model,
    )
    assert permission_builder is not None
    assert "category" not in permission_builder.group(0)


def test_query_engine_does_not_own_extension_dispatch_boundary():
    text = _read(ROOT / "src/embedagent_core/query_engine.py")
    assert "AgentExtensionHost(" in text
    forbidden_dispatches = (
        "self.extension_manager.allowed_tool_names(",
        "self.extension_manager.handle_tool_call(",
        "self.extension_manager.apply_tool_call_hooks(",
        "self.extension_manager.apply_tool_result_hooks(",
        "self.extension_manager.run_context_hooks(",
        "self.extension_manager.register_dynamic_tools(",
    )
    offenders = []
    for token in forbidden_dispatches:
        if token in text:
            offenders.append("query_engine.py directly dispatches %s" % token)
    assert offenders == []


def test_c_cpp_workflow_extension_stays_behind_default_package_boundary():
    allowed_files = set()
    allowed_prefixes = ("src/embedagent/workflow_packages/c_cpp/",)
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        rel = _relative(path)
        if rel in allowed_files or rel.startswith(allowed_prefixes):
            continue
        text = _read(path)
        for token in (
            "CHarnessWorkflowExtension",
            "embedagent.workflow_packages.c_cpp.extension",
        ):
            if token in text:
                offenders.append("%s imports or constructs %s" % (rel, token))
    assert offenders == []


def test_active_source_does_not_reintroduce_tooling_pack_aliases():
    forbidden = (
        "embedagent.tooling.packs",
        "from embedagent.tooling import BUILD_LITE_PACK",
        "from embedagent.tooling import CORE_PACK",
        "from embedagent.tooling import DEBUG_LITE_PACK",
        "from embedagent.tooling import VERIFY_PACK",
        "from embedagent.tooling import PACKS",
        "from embedagent.tooling import pack_tool_names",
    )
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        rel = _relative(path)
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    assert offenders == []


def test_local_resources_do_not_import_c_cpp_workflow_defaults():
    text = _read(ROOT / "src/embedagent/local_resources.py")
    forbidden = (
        "embedagent.workflow_packages.c_cpp",
        "C_WORKFLOW_TOOL_RUN_RECIPE",
    )
    offenders = [token for token in forbidden if token in text]
    assert offenders == []


def test_self_extension_authoring_does_not_import_c_cpp_workflow_defaults():
    text = _read(ROOT / "src/embedagent/self_extension_authoring.py")
    forbidden = (
        "embedagent.workflow_packages.c_cpp",
        "C_WORKFLOW_TOOL_RUN_RECIPE",
    )
    offenders = [token for token in forbidden if token in text]
    assert offenders == []


def _active_contract_doc_files():
    roots = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "docs",
    ]
    excluded_prefixes = (
        "docs/archive/",
        "docs/superpowers/",
    )
    excluded_files = {
        "docs/design-change-log.md",
        "docs/development-tracker.md",
    }
    result = []
    for root in roots:
        candidates = [root] if root.is_file() else list(root.rglob("*.md"))
        for path in candidates:
            rel = _relative(path)
            if rel in excluded_files:
                continue
            if any(rel.startswith(prefix) for prefix in excluded_prefixes):
                continue
            result.append(path)
    return result


def _doc_legacy_context_windows(text):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        start = max(0, index - 2)
        end = min(len(lines), index + 2)
        yield line, " ".join(item.strip() for item in lines[start:end] if item.strip())


def test_active_docs_keep_legacy_architecture_terms_in_removed_contexts():
    legacy_terms = (
        "manage" + "_to" + "dos",
        "mode=code",
        "timeline replay",
        "legacy harness" + "_prompt compatibility",
        "Session" + "TimelineStore",
        "HarnessStateSynchronizer",
        "embedagent.tooling.packs",
    )
    allowed_context_markers = (
        "archive",
        "archived",
        "current baseline",
        "do not",
        "does not",
        "forbidden",
        "guard",
        "guards",
        "has been deleted",
        "has been removed",
        "have been removed",
        "historical",
        "is not",
        "must not",
        "no longer",
        "not current",
        "not part of",
        "not treated",
        "no durable",
        "old",
        "obsolete",
        "removed",
        "stale",
        "there is no",
        "不再",
        "不得",
        "不属于",
        "历史",
        "已删除",
        "已移除",
        "禁止",
    )
    offenders = []
    for path in _active_contract_doc_files():
        rel = _relative(path)
        for line, context in _doc_legacy_context_windows(_read(path)):
            lowered_line = line.lower()
            lowered_context = context.lower()
            for term in legacy_terms:
                if term.lower() not in lowered_line:
                    continue
                if any(marker in lowered_context for marker in allowed_context_markers):
                    continue
                offenders.append("%s uses %s without removed/forbidden context" % (rel, term))
    assert offenders == []


def test_runtime_tool_execute_calls_stay_behind_action_or_hosted_services():
    allowed_files = {
        "src/embedagent/agent_tool_action_service.py",
        "src/embedagent_host/hosted_command_service.py",
        "src/embedagent/review_command.py",
    }
    allowed_prefixes = ("src/embedagent/tools/",)
    pattern = re.compile(r"\b(?:self\.)?tools\.execute\(")
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        rel = _relative(path)
        if rel in allowed_files or rel.startswith(allowed_prefixes):
            continue
        for line_number, line in enumerate(_read(path).splitlines(), start=1):
            if pattern.search(line):
                offenders.append("%s:%s calls ToolRuntime.execute" % (rel, line_number))
    assert offenders == []


def test_tool_refresh_paths_use_read_model_invalidations_not_tool_name_lists():
    tool_names = (
        "task_status",
        "report_quality_v2",
        "record_failing_evidence",
        "run_recipe",
        "list_recipes",
    )
    refresh_words = ("refresh", "invalidate", "invalidations", "tool_finished", "tool_result")
    allowed_prefixes = (
        "src/embedagent/workflow_packages/c_cpp/",
        "src/embedagent/tools/",
    )
    offenders = []
    for path in _source_files_under("src/embedagent"):
        rel = _relative(path)
        if rel.startswith(allowed_prefixes):
            continue
        for line_number, line in enumerate(_read(path).splitlines(), start=1):
            lowered = line.lower()
            if not any(name in line for name in tool_names):
                continue
            if not any(word in lowered for word in refresh_words):
                continue
            if "read_model_invalidations" in line or "readModelInvalidations" in line:
                continue
            offenders.append("%s:%s hard-codes workflow tool refresh" % (rel, line_number))
    assert offenders == []


def test_gui_timeline_tool_preview_is_catalog_driven():
    text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js")

    assert "commandPreviewFromToolPresentation" in text
    for token in (
        'if (toolName === "shell" || toolName === "bash")',
        'if (toolName === "grep_text")',
        'if (toolName === "glob_files")',
        'if (toolName === "read_file" || toolName === "write_file" || toolName === "edit_file")',
        "function toolNameRequestKind",
        "const WRITE_TOOLS",
        "WRITE_TOOLS.has",
        'commandName === "diff"',
        'commandName === "review"',
    ):
        assert token not in text


def test_gui_command_result_diff_surface_is_payload_driven():
    text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )

    assert 'type: "diff_surface_opened"' in text
    assert 'commandName === "diff"' not in text


def test_gui_command_result_session_switch_is_payload_driven():
    text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )

    assert "switch_session_id" in text
    assert 'commandName === "resume"' not in text


def test_gui_command_result_run_output_log_is_payload_driven():
    text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )

    assert "function commandLogPayload" in text
    assert "log_label" in text
    assert "logLabel" in text
    assert "command: /" not in text
    assert 'data?.success ? "ok" : "error"' not in text


def test_gui_command_result_timeline_labels_are_payload_or_chrome_declared():
    t3_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js")
    rows_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx"
    )

    assert "label: stringValue(item?.label)" in t3_text
    assert "`/${commandName}`" not in t3_text
    assert "`/${row.commandName" not in rows_text
    assert 'label={row.label || chrome.commandDefaultName || ""}' in rows_text


def test_gui_user_input_interactions_do_not_default_to_ask_user_tool():
    text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js"
    )

    assert 'sourceKind === "user-input.requested"' in text
    assert '|| "ask_user"' not in text


def test_gui_session_payloads_do_not_invent_chat_workflow_state():
    backend_text = _read(ROOT / "src/embedagent/frontend/gui/backend/protocol_payloads.py")
    frontend_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/state-helpers.js")

    assert 'read_value(snapshot, "workflow_state", "chat")' not in backend_text
    assert 'or "chat"' not in backend_text
    assert 'workflow_state: payload.workflow_state || "chat"' not in frontend_text


def test_gui_raw_interaction_requests_do_not_synthesize_activity_records():
    files = [
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js",
        ROOT / "src/embedagent/frontend/gui/webapp/src/store.js",
    ]
    activity_tokens = (
        "interaction" + ".created",
        "append_timeline_item",
        "append_activity_item",
        "turn_started",
        "tool_started",
        "assistant_delta",
    )
    offenders = []
    for path in files:
        rel = _relative(path)
        lines = _read(path).splitlines()
        for index, line in enumerate(lines):
            if "permission_request" not in line and "user_input_request" not in line:
                continue
            window = "\n".join(lines[index : index + 12])
            if any(token in window for token in activity_tokens):
                offenders.append(
                    "%s:%s synthesizes activity from raw interaction request" % (rel, index + 1)
                )
    assert offenders == []


def test_gui_pending_interaction_display_prefers_session_snapshot_not_raw_requests():
    store_path = ROOT / "src/embedagent/frontend/gui/webapp/src/store.js"
    socket_effects_path = (
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )
    activity_state_path = (
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js"
    )
    store_text = _read(store_path)
    socket_text = _read(socket_effects_path)
    activity_state_text = _read(activity_state_path)
    assert re.search(r"\n\s+permission\s*:", store_text) is None
    assert re.search(r"\n\s+userInput\s*:", store_text) is None
    assert 'case "permission_request"' not in store_text
    assert 'case "user_input_request"' not in store_text
    assert 'type: "permission_request"' not in socket_text
    assert 'type: "user_input_request"' not in socket_text
    assert "currentInteractionFromSnapshot(snapshot) || activityInteraction" in activity_state_text
    assert "currentInteractionFromActivities(timelineItems)" in activity_state_text
    assert "normalizePendingInteraction" not in activity_state_text
    assert not (
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/PermissionModal.jsx"
    ).exists()


def test_agent_application_capabilities_are_declared_by_backend_not_gui_defaults():
    adapter_text = _read(ROOT / "src/embedagent_host/inprocess_adapter.py")
    application_registry_text = _read(ROOT / "src/embedagent/agent_applications.py")
    protocol_text = _read(ROOT / "src/embedagent/protocol/app_protocol.py")
    normalizer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js"
    )
    no_workspace_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx"
    )

    assert "build_agent_application" in adapter_text
    assert "agentApplication" in adapter_text
    assert "agentApplications" in adapter_text
    assert "AgentApplicationRecord" in application_registry_text
    assert "BUILTIN_AGENT_APPLICATION_RECORDS" in application_registry_text
    assert "AgentApplicationDefinition" not in application_registry_text
    assert "_builtin_agent_application_definitions" not in application_registry_text
    assert "AgentApplicationDescriptor" in protocol_text
    assert "normalizeAgentApplicationDescriptor" in normalizer_text

    forbidden_gui_defaults = (
        "Default C/C++ Agent",
        "D:\\\\work\\\\project",
        "Open a project",
        "local workspace",
    )
    for token in forbidden_gui_defaults:
        assert token not in normalizer_text
        assert token not in no_workspace_text


def test_gui_app_shell_surfaces_are_descriptor_records_not_string_lists():
    app_shell_spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    app_model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    surfaces_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js")
    right_panel_tabs_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx"
    )

    for token in (
        '_surface(\n                "files"',
        '_surface(\n                "terminal"',
        '"launcher_order"',
    ):
        assert token in app_shell_spec_text
    assert "surface_chrome" in app_shell_spec_text
    assert "command_label" in app_shell_spec_text
    assert "normalizeSurfaceCapability" in app_model_text
    assert "normalizeSurfaceChrome" in app_model_text
    assert "surfaceCapabilityDefinitions" in surfaces_text
    assert "surfaceChromeLabels" in surfaces_text
    assert "surfaceChromeLabels(appCapabilities)" in right_panel_tabs_text
    assert "hasDisplayTitle" in surfaces_text
    assert "&& hasDisplayTitle(definition)" in surfaces_text
    assert "label: definition.commandLabel" in surfaces_text
    assert "`Open ${definition.title}`" not in surfaces_text
    assert "String(input.title || kind)" not in app_model_text
    assert (
        'return definition && definition.title ? definition.title : String(kind || "");'
        not in surfaces_text
    )
    assert '|| "file"' not in surfaces_text
    assert '|| "preview"' not in surfaces_text
    assert '|| "terminal"' not in surfaces_text
    assert 'value.map((item) => String(item || ""))' not in surfaces_text
    for registry_copy in (
        'title: "Preview"',
        'title: "Diff"',
        'title: "Files"',
        'title: "Terminal"',
        'title: "Plan"',
        'title: "Source Control"',
        'title: "Settings"',
        'title: "Diagnostics"',
        'title: "Run Output"',
        'commandLabel: "Open Terminal"',
        'commandLabel: "Toggle Run Output"',
        'description: "',
    ):
        assert registry_copy not in surfaces_text
    for hardcoded_copy in (
        '"Right panel"',
        '"Add panel surface"',
        '"Open a surface"',
        '"Choose what to show in the right panel."',
        '"Surface actions for"',
        '"Close others"',
        '"Close to the right"',
        '"Close all"',
    ):
        assert hardcoded_copy not in right_panel_tabs_text


def test_gui_surface_registry_does_not_export_fixed_surface_id_lists():
    surfaces_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js")
    ui_state_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js")

    for token in (
        "export const RIGHT_PANEL_KINDS",
        "export const RIGHT_PANEL_SURFACES",
        "export const BOTTOM_DRAWER_SURFACES",
    ):
        assert token not in surfaces_text
    for token in (
        "RIGHT_PANEL_KINDS",
        "RIGHT_PANEL_SURFACES",
        "BOTTOM_DRAWER_SURFACES",
    ):
        assert token not in ui_state_text
    assert "supportedSurfaceKinds(" in ui_state_text


def test_gui_keybindings_are_app_shell_declared_not_renderer_defaults():
    app_shell_spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    app_model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    keybindings_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js"
    )

    assert '"keybindings": _copy_records(self.keybindings)' in app_shell_spec_text
    assert '_keybinding("mod+k", "palette.open", "not_palette")' in app_shell_spec_text
    assert "normalizeKeybinding" in app_model_text
    assert "state.app.capabilities.keybindings" in app_text
    assert "DEFAULT_KEYBINDINGS" not in app_text
    assert "DEFAULT_KEYBINDINGS" not in keybindings_text


def test_gui_app_shell_projects_active_agent_application_capabilities():
    app_shell_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell.py")
    app_model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")

    assert "get_session_capabilities" in app_shell_text
    assert '"agentApplication"' in app_shell_text
    assert '"agentApplications"' in app_shell_text
    assert "normalizeAgentApplicationDescriptor" in app_model_text
    assert "state.app.capabilities?.emptyState" in app_text


def test_gui_app_shell_projects_selected_agent_application_before_workspace():
    app_host_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_host.py")
    app_shell_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell.py")
    launcher_text = _read(ROOT / "src/embedagent/frontend/gui/launcher.py")
    adapter_text = _read(ROOT / "src/embedagent_host/inprocess_adapter.py")
    registry_text = _read(ROOT / "src/embedagent/agent_applications.py")

    assert "def agent_application_capability_payload" in registry_text
    assert "def agent_capabilities" in app_host_text
    assert "host_agent_capabilities" in app_shell_text
    assert "_project_agent_capabilities" in app_shell_text
    assert "agent_application_capability_payload" in launcher_text
    assert "agent_application_capability_payload" in adapter_text
    assert "available_agent_application_manifests" not in adapter_text


def test_gui_app_home_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    app_model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_home_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js"
    )
    sidebar_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx")
    no_workspace_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx"
    )

    assert '"home": _copy_value(self.home)' in spec_text
    assert "normalizeHomeCopy" in app_model_text
    assert "home: normalizeHomeCopy" in app_model_text
    assert "app.capabilities?.home" in app_home_text
    assert "productName" in app_home_text
    assert "appHome?.productName" in no_workspace_text
    assert '"EmbedAgent"' not in app_model_text
    assert ">EmbedAgent<" not in no_workspace_text
    for hardcoded_copy in (
        '"No workspace"',
        '"Open a local project"',
        '"Workspace path"',
        '"Missing path"',
        '"No threads yet"',
        '"Start one for this project."',
    ):
        assert hardcoded_copy not in app_home_text
        assert hardcoded_copy not in sidebar_text
        assert hardcoded_copy not in no_workspace_text


def test_gui_app_shell_service_uses_injected_spec_not_inline_descriptor_lists():
    app_shell_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell.py")
    spec_path = ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py"

    assert spec_path.exists()
    assert "default_app_shell_spec" in app_shell_text
    for token in (
        "def _keybindings",
        "def _right_panel_surfaces",
        "def _bottom_drawer_surfaces",
        '"app.settings"',
        '"surface.files"',
    ):
        assert token not in app_shell_text


def test_gui_app_shell_commands_are_descriptor_records_not_string_lists():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    commands_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/commands.js")
    protocol_normalizer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js"
    )
    app_shell_commands_path = ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/commands.js"

    assert "def _command(" in spec_text
    assert '"app_commands": _copy_records(self.app_commands)' in spec_text
    assert '"workspace_commands": _copy_records(self.workspace_commands)' in spec_text
    assert '"workbench_commands": _copy_records(self.workbench_commands)' in spec_text
    assert "normalizeAppCommandDescriptor" in model_text
    assert "appCommands: normalizeAppCommandDescriptors" in model_text
    assert "workspaceCommands: normalizeAppCommandDescriptors" in model_text
    assert "workbenchCommands: normalizeAppCommandDescriptors" in model_text
    assert "WORKSPACE_COMMANDS" not in commands_text
    assert "LOCAL_COMMANDS" not in commands_text
    assert "WORKBENCH_COMMANDS" not in commands_text
    assert "workflow.diff" not in commands_text
    assert "String(input.label || id).trim() || id" not in model_text
    assert "item.label || item.usage || id" not in commands_text
    assert "!command.label" in commands_text
    assert "firstText(data.label, data.usage, id)" not in protocol_normalizer_text
    assert "filterCommandsByCapability" not in commands_text
    assert "APP_COMMANDS" not in commands_text
    assert not app_shell_commands_path.exists()


def test_gui_command_palette_groups_are_app_shell_descriptors():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    palette_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js"
    )
    palette_component_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPalette.jsx"
    )
    palette_results_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/workbench/CommandPaletteResults.jsx"
    )
    commands_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/commands.js")

    assert "command_palette_groups" in spec_text
    assert "command_palette_labels" in spec_text
    assert '"command_palette": {' in spec_text
    assert "def _palette_group(" in spec_text
    assert "normalizePaletteGroupDescriptor" in model_text
    assert "rootPlaceholder" in model_text
    assert "commandPalette: normalizeCommandPalette" in model_text
    assert "GROUP_TITLES" not in palette_model_text
    assert "GROUP_DESCRIPTIONS" not in palette_model_text
    assert "paletteGroupDescriptors" in palette_model_text
    assert "paletteLabels" in palette_model_text
    assert "asText(command.label) || asText(command.id)" not in palette_model_text
    assert "asText(command.group) === targetGroup && asText(command.label)" in palette_model_text
    assert '"Command palette"' not in palette_component_text
    assert '"Search commands, sessions, workspaces"' not in palette_component_text
    assert '"No matching commands, sessions, or workspaces"' not in palette_component_text
    assert '"No matching commands, sessions, or workspaces"' not in palette_results_text
    assert 'emptyLabel = ""' in palette_results_text
    assert '"Current"' not in palette_model_text
    assert '"Missing"' not in palette_model_text
    assert '"Workspace"' not in palette_model_text
    assert "COMMAND_GROUPS" not in commands_text


def test_gui_chrome_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    header_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx"
    )
    sidebar_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Sidebar.jsx")
    composer_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Composer.jsx")
    interaction_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/interaction-model.js"
    )
    approval_panel_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingApprovalPanel.jsx"
    )
    approval_actions_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingApprovalActions.jsx"
    )
    user_input_panel_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/composer/ComposerPendingUserInputPanel.jsx"
    )
    surface_panel_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )

    assert "chrome: Dict[str, Any]" in spec_text
    assert '"chrome": _copy_value(self.chrome)' in spec_text
    assert '"brand_subtitle": "Local agent workbench"' in spec_text
    assert "normalizeChrome" in model_text
    assert "normalizeInteractionChrome" in model_text
    assert "chrome: normalizeChrome(input)" in model_text
    assert "appChrome" in app_text
    assert "chrome={appChrome.header || {}}" in app_text
    assert "chrome={appChrome}" in app_text
    assert "chrome={appChrome.composer || {}}" in app_text
    assert "chrome: appChrome.surfacePanel || {}" in app_text
    assert "set_lang" not in store_text
    assert "lang:" not in store_text

    assert not (ROOT / "src/embedagent/frontend/gui/webapp/src/LangContext.js").exists()
    assert not (ROOT / "src/embedagent/frontend/gui/webapp/src/strings.js").exists()
    assert not (
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/InteractionPanel.jsx"
    ).exists()

    for text in (app_text, header_text, sidebar_text, composer_text, surface_panel_text):
        assert "strings.js" not in text
        assert "LangContext" not in text
        assert "useLang" not in text

    assert "lang-toggle" not in header_text
    assert "chrome.commandPaletteShortLabel" in header_text
    assert "chrome.brandSubtitle" in sidebar_text
    assert "chrome.placeholder" in composer_text
    assert "chrome={chrome.interaction || {}}" in composer_text
    assert "hintLabels[hint.id]" in composer_text
    assert "summaryForPermission(kind, copy = {})" in interaction_model_text
    assert '"Command approval requested"' not in interaction_model_text
    assert '"Approve once"' not in interaction_model_text
    assert '"Input requested"' not in interaction_model_text
    assert "approval.kicker" in approval_panel_text
    assert "approval.cancelLabel" in approval_actions_text
    assert "approval.rememberLabel" in approval_actions_text
    assert "prompt.kicker" in user_input_panel_text
    assert "prompt.submitLabel" in user_input_panel_text
    for token in (
        "PENDING APPROVAL",
        "INPUT REQUIRED",
        "Cancel turn",
        "Always allow this session",
        "Submit",
    ):
        assert token not in approval_panel_text
        assert token not in approval_actions_text
        assert token not in user_input_panel_text
    assert "chrome.settingsTitle" in surface_panel_text
    assert "diagnosticGroups[row.group]" in surface_panel_text


def test_gui_composer_menu_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    composer_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Composer.jsx")
    menu_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/composer/ComposerCommandMenu.jsx"
    )
    command_search_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/composer/composer-command-search.js"
    )
    path_context_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/composer/composer-path-context.js"
    )
    interaction_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/composer/composer-interaction-model.js"
    )

    assert '"command_menu": {' in spec_text
    assert '"path_group_label": "Files"' in spec_text
    assert "normalizeComposerCommandMenuChrome" in model_text
    assert "commandMenu: normalizeComposerCommandMenuChrome" in model_text
    assert "composerCommandGroupLabels" in app_text
    assert "commandGroupLabels={composerCommandGroupLabels}" in app_text
    assert "const commandMenuChrome = chrome.commandMenu || {}" in composer_text
    assert "commandGroupLabels" in composer_text
    assert "chrome={commandMenuChrome}" in composer_text
    assert "chrome.pathAriaLabel" in menu_text
    assert "chrome.pathItemKindLabel" in menu_text
    assert "commandMenuChrome.pathGroupLabel" in path_context_text
    assert "commandMenuChrome.commandEmptyText" in interaction_model_text
    assert "commandGroupLabels" in command_search_text
    assert "GROUP_LABELS" not in command_search_text

    for hardcoded_copy in (
        '"Files"',
        '"Command"',
        '"No files found"',
        '"No commands found"',
        '"No matches"',
        '"File context suggestions"',
        '"Slash command suggestions"',
        ">file<",
        ">command<",
    ):
        assert hardcoded_copy not in menu_text
        assert hardcoded_copy not in command_search_text
        assert hardcoded_copy not in path_context_text
        assert hardcoded_copy not in interaction_model_text


def test_gui_timeline_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    timeline_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx")
    timeline_rows_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/timeline/TimelineRows.jsx"
    )
    work_row_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/timeline/WorkRow.jsx"
    )
    tool_detail_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/timeline/ToolDetail.jsx"
    )
    t3_timeline_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js"
    )
    changed_files_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/timeline/ChangedFilesCard.jsx"
    )

    assert '"timeline": {' in spec_text
    assert '"tool_detail": {' in spec_text
    assert '"work_row": {' in spec_text
    assert "normalizeTimelineChrome" in model_text
    assert "normalizeTimelineToolDetailChrome" in model_text
    assert "normalizeTimelineWorkRowChrome" in model_text
    assert "timeline: normalizeTimelineChrome" in model_text
    assert "chrome={appChrome.timeline || {}}" in app_text
    assert "chrome.historyPartialLabel" in timeline_text
    assert "chrome.historyUnavailable" in timeline_text
    assert "changedFilesChrome" in timeline_rows_text
    assert "workGroupChrome" in timeline_rows_text
    assert "activityRowsChrome" in timeline_rows_text
    assert "toolDetailChrome" in timeline_rows_text
    assert "workRowChrome" in timeline_rows_text
    assert "toolDetailChrome" in work_row_text
    assert "workRowChrome" in work_row_text
    assert "statusLabels" in work_row_text
    assert "defaultHeading" in work_row_text
    assert "defaultIconName" in work_row_text
    assert "fieldLabel" in tool_detail_text
    assert "sectionTitle" in tool_detail_text
    assert "fallbackMatchLabel" in tool_detail_text
    assert "chrome.streamingStatus" in timeline_rows_text
    assert "chrome.contextSummarizedTemplate" in timeline_rows_text
    assert "chrome.contextSizeTemplate" in timeline_rows_text
    assert "chrome.commandCompletedStatus" in timeline_rows_text
    assert "chrome.summaryTemplate" in changed_files_text
    assert "chrome.viewDiffLabel" in changed_files_text
    assert "completedAt: turnEndTimestamp" in t3_timeline_text
    assert "interrupted: hasInterruptedWork" in t3_timeline_text

    for hardcoded_copy in (
        "Conversation",
        "No conversation yet.",
        "history partially restored",
        "restore stopped early",
        "session history unavailable",
        "Explicit loop safety limit reached.",
        "Maximum turn limit reached",
        "Stopped by guard.",
        "Cancelled.",
    ):
        assert hardcoded_copy not in timeline_text

    for hardcoded_copy in (
        "1 tool call",
        "tool calls",
        "Show fewer tool calls",
        "previous tool",
        "Working...",
        "Working for",
        "Worked for this turn",
        " steps",
        '"Thinking"',
        "Context updated",
        " summarized",
        " retained",
        " tokens",
        "failed",
        '"completed"',
        "1 finding",
        " findings",
        "0s",
    ):
        assert hardcoded_copy not in timeline_rows_text

    for hardcoded_copy in (
        "Worked for ",
        "Worked for this turn",
        "You stopped after",
        "You stopped this response",
        '"Thinking"',
        "Context compacted",
        'label: "/review"',
        'title: "Error"',
        'title: "Preview"',
        'title: "Summary"',
        'title: "Matches"',
        'title: "Files"',
        'title: "stdout"',
        'title: "stderr"',
        'title: "Diff"',
        'title: "Changed files"',
    ):
        assert hardcoded_copy not in t3_timeline_text

    for hardcoded_copy in (
        'base || "Tool"',
        '"Work"',
        'return "zap"',
    ):
        assert hardcoded_copy not in t3_timeline_text

    for hardcoded_copy in (
        '"Detail"',
        '|| "match"',
    ):
        assert hardcoded_copy not in tool_detail_text

    for hardcoded_copy in (
        'return "failed"',
        'return "completed"',
        'return "empty"',
        'return "cancelled"',
        'return "skipped"',
        '"Work"',
        'iconName: "zap"',
    ):
        assert hardcoded_copy not in work_row_text

    for hardcoded_copy in (
        "View diff",
        '"Collapse"',
        '"Expand"',
        " changed files",
    ):
        assert hardcoded_copy not in changed_files_text


def test_gui_terminal_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js"
    )
    labels_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/terminal/terminal-labels.js")
    api_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/terminal/terminal-api.js")
    shell_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/TerminalShell.jsx"
    )
    surface_body_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx"
    )
    bottom_drawer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx"
    )

    assert '"chrome": {' in spec_text
    assert '"session_required_notice": "Open a session before using the terminal."' in spec_text
    assert "normalizeTerminalChrome" in model_text
    assert "chrome: normalizeTerminalChrome" in model_text
    assert "getTerminalChrome" in app_text
    assert "terminalChrome={terminalChrome}" in app_text
    assert "terminalChromeText" in controller_text
    assert "surfaceDefinitionFor" in controller_text
    assert "terminalChrome" in shell_text
    assert "terminalChrome" in surface_body_text
    assert "terminalChrome" in bottom_drawer_text
    assert '"Terminal request failed"' not in api_text

    for hardcoded_copy in (
        '"Open a session before using the terminal."',
        '"Terminal failed to open."',
        '"Terminal write failed."',
        '"Terminal clear failed."',
        '"Terminal restart failed."',
        '"Terminal close failed."',
        '"Terminal"',
        "`Terminal ${match[1]}`",
        '"New terminal"',
        '"Split terminal horizontally"',
        '"Split terminal vertically"',
        '"Terminal session is unavailable."',
        '"Type a command"',
        '"No terminal sessions for this thread yet."',
        '"Drawer"',
    ):
        assert hardcoded_copy not in controller_text
        assert hardcoded_copy not in labels_text
        assert hardcoded_copy not in shell_text


def test_gui_preview_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    preview_surface_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/PreviewSurface.jsx"
    )
    preview_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/preview-surface-model.js"
    )
    preview_api_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/preview/preview-api.js")
    surface_body_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx"
    )

    assert '"preview": _copy_value(self.preview)' in spec_text
    assert '"session_required_notice": "Open a session before using preview."' in spec_text
    assert "normalizePreviewChrome" in model_text
    assert "preview: normalizePreviewCapability" in model_text
    assert "previewChrome.sessionRequiredNotice" in app_text
    assert "previewCapability.localServers" in app_text
    assert "previewChrome={previewChrome}" in app_text
    assert "previewServers={previewCapability.localServers" in app_text
    assert "previewChrome" in surface_body_text
    assert "previewServers" in surface_body_text
    assert "previewChrome" in preview_surface_text
    assert "chrome.statusReady" in preview_model_text
    assert "chrome.emptyTitle" in preview_model_text
    assert '"Preview request failed"' not in preview_api_text

    for hardcoded_copy in (
        '"Open a session before using preview."',
        '"Preview failed"',
        '"Preview refresh failed"',
        '"Open preview failed"',
    ):
        assert hardcoded_copy not in app_text

    for hardcoded_copy in (
        '"Vite dev server"',
        '"Local app"',
        '"Loading..."',
        '"Refresh"',
        '"Loading preview"',
        '"Refresh preview"',
        '"Search or enter URL"',
        '"Preview URL"',
        '"Open in system browser"',
        '"Annotate preview"',
        '"More preview actions"',
        '"Preview unavailable"',
        '"This local page cannot be rendered in the embedded preview."',
        '"The local preview target did not respond."',
        '"Reload"',
        '"Preview failed"',
    ):
        assert hardcoded_copy not in preview_surface_text

    for hardcoded_copy in (
        '"Loading"',
        '"Ready"',
        '"Preview unavailable"',
        '"Idle"',
        '"Local server"',
        '"Local servers"',
        '"No preview open"',
        '"Choose a local server to open in the preview panel."',
        '"Start a local dev server or enter a localhost URL above."',
    ):
        assert hardcoded_copy not in preview_model_text


def test_gui_file_preview_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    right_panel_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js"
    )
    surface_body_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx"
    )
    file_preview_surface_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/FilePreviewSurface.jsx"
    )
    file_preview_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/file-preview-model.js"
    )

    assert '"file_preview": {' in spec_text
    assert '"loading_message": "Loading file..."' in spec_text
    assert "normalizeFilePreviewChrome" in model_text
    assert "filePreview: normalizeFilePreviewChrome" in model_text
    assert "filePreviewChrome.unavailableMessage" in app_text
    assert "fileSurfaceTitle(filePath, filePreviewChrome)" in app_text
    assert "fileSurfaceTitle(path, filePreviewChrome" in right_panel_controller_text
    assert "filePreviewChrome={filePreviewChrome}" in surface_body_text
    assert "filePreviewChrome" in file_preview_surface_text
    assert "chrome.languageLabels" in file_preview_model_text

    for hardcoded_copy in (
        '"File unavailable"',
        '"Loading file..."',
        ">Retry<",
        '"Show markdown source"',
        '"Show rendered markdown"',
        '"Show file explorer"',
    ):
        assert hardcoded_copy not in app_text
        assert hardcoded_copy not in store_text
        assert hardcoded_copy not in file_preview_surface_text
        assert hardcoded_copy not in right_panel_controller_text

    for hardcoded_copy in (
        '"File"',
        '"Workspace"',
        '"Plain"',
        '"Markdown"',
        '"TypeScript"',
    ):
        assert hardcoded_copy not in file_preview_model_text


def test_gui_files_surface_title_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    files_surface_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/FilesSurface.jsx"
    )
    surface_body_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx"
    )

    assert '_surface(\n                "files",' in spec_text
    assert '"Files"' in spec_text
    assert "surface?.title" in files_surface_text
    assert "surface={surface}" in surface_body_text
    assert "<strong>Files</strong>" not in files_surface_text


def test_gui_diff_panel_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    surface_panel_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )
    diff_panel_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/diff/DiffPanel.jsx"
    )
    diff_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/diff-model.js"
    )
    socket_effects_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")

    assert '"diff_panel": {' in spec_text
    assert "normalizeDiffPanelChrome" in model_text
    assert "diffPanel: normalizeDiffPanelChrome" in model_text
    assert "diffPanelChrome" in app_text
    assert "diffPanelChrome" in surface_panel_text
    assert "chrome.selectionAriaLabel" in diff_panel_text
    assert "chrome.expandDiffLabel" in diff_panel_text
    assert "chromeDefaultTitle" in diff_model_text
    assert "diffPanelChrome" in socket_effects_text

    for hardcoded_copy in (
        "No diff selected.",
        "Diff selection",
        "Diff controls",
        "Stacked diff view",
        "Split diff view",
        "Disable line wrapping",
        "Enable line wrapping",
        "Show whitespace changes",
        "Hide whitespace changes",
        "Changed files",
        ">Files<",
        "Expand diff",
    ):
        assert hardcoded_copy not in diff_panel_text

    assert '"Git Diff"' not in app_text
    assert "`Git Diff:" not in app_text
    assert '"Git Diff"' not in socket_effects_text
    assert 'title: action.diffSurface?.title || "diff"' not in store_text


def test_gui_source_control_copy_is_app_shell_declared():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    surface_panel_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )
    source_control_panel_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/source-control/SourceControlPanel.jsx"
    )
    source_control_state_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/source-control/source-control-state.js"
    )
    source_control_presentation_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/source-control/source-control-presentation.js"
    )
    source_control_api_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/source-control/source-control-api.js"
    )
    branch_toolbar_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/BranchToolbar.jsx"
    )
    branch_toolbar_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/source-control/branch-toolbar-model.js"
    )

    assert '"source_control": _copy_value(self.source_control)' in spec_text
    assert '"status_unavailable_notice": "Source control unavailable."' in spec_text
    assert '"branch_toolbar": {' in spec_text
    assert "normalizeSourceControlChrome" in model_text
    assert "chrome: normalizeSourceControlChrome" in model_text
    assert "branchToolbar: normalizeBranchToolbarChrome" in model_text
    assert "sourceControlChrome.statusUnavailableNotice" in app_text
    assert "sourceControlChrome.diffUnavailableNotice" in app_text
    assert "sourceControlChrome" in app_text
    assert "sourceControlChrome" in surface_panel_text
    assert "sourceControlChrome" in source_control_panel_text
    assert "chrome.groupLabels" in source_control_presentation_text
    assert "chrome.providerLabels" in source_control_presentation_text
    assert "model.branchMetaLabel" in branch_toolbar_text
    assert "sourceControlChrome?.branchToolbar" in branch_toolbar_model_text
    assert '"Source control request failed"' not in source_control_api_text

    for hardcoded_copy in (
        '"Source control unavailable"',
        '"Diff unavailable"',
    ):
        assert hardcoded_copy not in app_text
        assert hardcoded_copy not in source_control_state_text

    for hardcoded_copy in (
        '"Source control unavailable."',
        '"Loading changes..."',
        '"Git runtime is not available for this workspace."',
        '"The active workspace is not a Git repository."',
        '"No local changes."',
        '"No branch"',
        '"Refresh"',
    ):
        assert hardcoded_copy not in source_control_panel_text

    for hardcoded_copy in (
        '"Checking Git..."',
        '"Git status unavailable"',
        '"Git unavailable"',
        '"No repository"',
        '"Unknown ref"',
        '"Clean"',
        '"Current checkout"',
        '"Run in the active workspace checkout."',
        '"Git is unavailable in this offline bundle or workspace."',
        '"This workspace is not a Git repository."',
        '"Git status is unavailable."',
    ):
        assert hardcoded_copy not in branch_toolbar_model_text

    for hardcoded_copy in (
        '"This action is read-only in the current GUI shell."',
        ">Worktree<",
        ">Branch<",
        '"Refresh local Git status"',
    ):
        assert hardcoded_copy not in branch_toolbar_text


def test_gui_thread_lifecycle_actions_are_backend_descriptors():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    app_home_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js"
    )
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/thread-lifecycle-controller.js"
    )

    assert "thread_lifecycle_actions" in spec_text
    assert "prompt_title" in spec_text
    assert "confirm_title" in spec_text
    assert "success_title" in spec_text
    assert "normalizeThreadLifecycleAction" in model_text
    assert "promptTitle" in model_text
    assert "confirmTitle" in model_text
    assert "successTitle" in model_text
    assert "actions: normalizeThreadLifecycleActions" in model_text
    assert "reasonLabel" in model_text
    assert "label: String(input.label || id)" not in model_text
    assert "getThreadLifecycleCapabilities" in controller_text
    assert "promptTitle" in controller_text
    assert "confirmTitle" in controller_text
    assert "successTitle" in controller_text
    assert "emptyTitle" in controller_text
    assert "failureTitle" in controller_text
    assert 'actionText(action, "emptyTitle")' in controller_text
    assert 'actionText(action, "failureTitle")' in controller_text
    assert "${action.label} failed" not in controller_text
    assert "label: id" not in controller_text
    assert '"Rename thread"' not in controller_text
    assert '"Archive this thread?"' not in controller_text
    assert '"Fork thread title"' not in controller_text
    assert '"Thread archived"' not in controller_text
    assert "THREAD_LIFECYCLE_ACTIONS" not in app_home_text
    assert "if (!label) return null" in app_home_text
    assert ".filter(Boolean)" in app_home_text
    assert "Backend lifecycle API is not available yet" not in app_home_text
    assert "Thread is missing" not in app_home_text
    assert "label: String(action?.label || actionId)" not in app_home_text
    assert 'label: "Rename"' not in app_home_text
    assert 'label: "Fork"' not in app_home_text
    assert 'label: "Archive"' not in app_home_text


def test_agent_core_has_no_harness_prompt_or_command_name_validation_coupling():
    extensions_text = _read(ROOT / "src/embedagent_core/extensions.py")
    turn_experience_text = _read(ROOT / "src/embedagent_core/turn_experience.py")

    assert "HarnessPrompt" not in extensions_text
    assert "_looks_like_validation" not in turn_experience_text
    for command_marker in ("ctest", "ninja", "cmake", "clang", "gcc"):
        assert command_marker not in turn_experience_text


def test_gui_default_mode_is_backend_declared():
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    state_helpers_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/state-helpers.js")
    session_loaders_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js"
    )
    activity_state_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js"
    )
    command_palette_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/command-palette-model.js"
    )
    gui_routes_text = _read(ROOT / "src/embedagent/frontend/gui/backend/routes_sessions.py")
    gui_protocol_text = _read(ROOT / "src/embedagent/frontend/gui/backend/protocol_payloads.py")
    core_adapter_text = _read(ROOT / "src/embedagent/core/adapter.py")

    assert 'DEFAULT_MODE = "explore"' not in store_text
    assert 'defaultMode = "explore"' not in state_helpers_text
    assert 'options.defaultMode || "explore"' not in session_loaders_text
    assert 'defaultMode = "explore"' not in activity_state_text
    assert 'session.current_mode || session.mode || "explore"' not in command_palette_text
    assert "DEFAULT_MODE" not in gui_routes_text
    assert "DEFAULT_MODE" not in gui_protocol_text
    assert "DEFAULT_MODE" not in core_adapter_text
    assert 'current_mode=snapshot.get("current_mode") or' not in core_adapter_text


def test_gui_tool_presentation_is_catalog_driven():
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    tool_presentation_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/tool-presentation.js"
    )

    assert "TOOL_LABELS" not in store_text
    assert "export function toolLabel" not in store_text
    assert "Read  " not in store_text
    assert "Write  " not in store_text
    assert "Git status" not in store_text
    assert "resolveToolPresentation" in tool_presentation_text
    assert "label: text(source.label, name)" in tool_presentation_text


def test_gui_has_no_split_task_or_recipe_refetch_contracts():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    session_loaders_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js"
    )
    socket_effects_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )
    gui_routes_text = _read(ROOT / "src/embedagent/frontend/gui/backend/routes_sessions.py")
    gui_server_text = _read(ROOT / "src/embedagent/frontend/gui/backend/server.py")
    protocol_text = _read(ROOT / "src/embedagent/protocol/__init__.py")
    inspector_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )
    styles_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/styles.css")

    for token in (
        "/api/tasks",
        "/api/workspace/recipes",
        "loadTasks",
        "loadWorkspaceRecipes",
        "tasks_loaded",
        "recipes_loaded",
        "LOAD_TASKS",
        "tasks_refresh",
        "on_tasks_refresh",
        "RunPanel",
        "RecipeCard",
        "onRunRecipe",
        "recipe-",
    ):
        assert token not in app_text
        assert token not in store_text
        assert token not in session_loaders_text
        assert token not in socket_effects_text
        assert token not in gui_routes_text
        assert token not in gui_server_text
        assert token not in protocol_text
        assert token not in inspector_text
        assert token not in styles_text


def test_gui_core_interface_has_no_split_task_or_recipe_facade():
    protocol_text = _read(ROOT / "src/embedagent/protocol/__init__.py")
    core_adapter_text = _read(ROOT / "src/embedagent/core/adapter.py")

    for token in (
        "def list_workspace_recipes",
        "def list_tasks",
    ):
        assert token not in protocol_text
        assert token not in core_adapter_text


def test_gui_has_no_split_tool_catalog_facade():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    app_workspaces_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-workspaces.js")
    routes_text = _read(ROOT / "src/embedagent/frontend/gui/backend/routes_sessions.py")
    protocol_text = _read(ROOT / "src/embedagent/protocol/__init__.py")
    core_adapter_text = _read(ROOT / "src/embedagent/core/adapter.py")

    for token in (
        "/api/tool-catalog",
        "loadToolCatalog",
        "tool_catalog_loaded",
        "state.toolCatalog",
        "toolCatalog: {}",
        "def get_tool_catalog",
    ):
        assert token not in app_text
        assert token not in store_text
        assert token not in app_workspaces_text
        assert token not in routes_text
        assert token not in protocol_text
        assert token not in core_adapter_text


def test_gui_workbench_entrypoints_are_app_capability_driven():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    commands_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/commands.js")
    ui_state_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js")
    keybindings_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js"
    )
    inspector_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )
    right_panel_tabs_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx"
    )
    bottom_drawer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx"
    )
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-command-controller.js"
    )

    assert "appCapabilities" in commands_text
    assert "surfaceCommandDefinitions(appCapabilities)" in commands_text
    assert "bottomDrawerCommandDefinitions(appCapabilities)" in commands_text
    assert "if (declared === null) return commands" not in commands_text
    assert "sanitizeWorkbenchUiStateForAppCapabilities" in store_text
    assert "sanitizeWorkbenchUiStateForAppCapabilities" in ui_state_text
    assert "rightPanelLauncherSurfaceDefinitions(appCapabilities)" in ui_state_text
    assert "bottomDrawerSurfaceDefinitions(appCapabilities)" in ui_state_text
    assert "appCapabilities" in keybindings_text
    assert "rightPanelLauncherSurfaceDefinitions(appCapabilities)" in right_panel_tabs_text
    assert "bottomDrawerSurfaceDefinitions(appCapabilities)" in bottom_drawer_text
    assert "surfaceChromeLabels" in bottom_drawer_text
    assert "chrome.bottomDrawerAriaLabel" in bottom_drawer_text
    assert "chrome.runOutputEmptyMessage" in bottom_drawer_text
    assert "chrome.terminationReasonPrefix" in bottom_drawer_text
    assert '"Bottom drawer"' not in bottom_drawer_text
    assert '"No run output yet."' not in bottom_drawer_text
    assert "reason={terminationReason}" not in bottom_drawer_text
    assert "if (allowed === null) return ordered" not in _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js"
    )
    for token in (
        "RIGHT_PANEL_SURFACES",
        "function InspectorTabs",
        "showTabs",
        "onTabChange",
    ):
        assert token not in inspector_text
        assert token not in app_text
    for token in (
        'onKindSelect("terminal")',
        'onKindSelect("run_output")',
        'onKindSelect("logs")',
    ):
        assert token not in bottom_drawer_text
    for token in (
        'case "app.settings"',
        'case "app.diagnostics"',
        'case "app.source_control"',
    ):
        assert token not in controller_text


def test_gui_has_no_root_inspector_navigation_state():
    checked_paths = (
        ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx",
        ROOT / "src/embedagent/frontend/gui/webapp/src/store.js",
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js",
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js",
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js",
    )
    banned_tokens = (
        "inspectorTab",
        "inspectorOpen",
        "set_inspector",
        "toggle_inspector",
    )
    for path in checked_paths:
        text = _read(path)
        for token in banned_tokens:
            assert token not in text


def test_gui_webapp_source_uses_right_panel_surface_vocabulary():
    checked_paths = (
        ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx",
        ROOT / "src/embedagent/frontend/gui/webapp/src/styles.css",
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx",
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/WorkbenchHeader.jsx",
    )
    forbidden_tokens = (
        "--inspector-w-raw",
        "inspector-toggle",
        "header.toggleInspector",
        "inspector.",
        'className="inspector"',
        'className="inspector-body"',
        ".inspector",
        ".inspector-tabs",
        ".insp-tab",
        "INSPECTOR",
    )
    offenders = []
    for path in checked_paths:
        text = _read(path)
        for token in forbidden_tokens:
            if token in text:
                offenders.append("%s contains %s" % (path.relative_to(ROOT), token))

    assert offenders == []


def test_gui_has_no_retired_inspector_sidecar_state():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    inspector_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )
    loaders_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js"
    )
    activation_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js"
    )
    socket_effects_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )
    interaction_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js"
    )

    for token in (
        "artifacts_loaded",
        '"preview_loaded"',
        '"review_loaded"',
        "permission_context_loaded",
        "LOAD_ARTIFACTS",
        "LOAD_PERMISSION_CONTEXT",
        "loadArtifacts",
        "loadPermissionContext",
        "/api/artifacts",
        "/api/permissions",
    ):
        assert token not in app_text
        assert token not in store_text
        assert token not in loaders_text
        assert token not in activation_text
        assert token not in socket_effects_text
        assert token not in interaction_text

    for token in (
        'inspectorTab === "tasks"',
        'inspectorTab === "artifacts"',
        'inspectorTab === "problems"',
        'inspectorTab === "review"',
        'inspectorTab === "permissions"',
        'inspectorTab === "runtime"',
        'inspectorTab === "preview"',
        'inspectorTab === "log"',
        "TaskPanel",
        "ArtifactPanel",
        "ProblemsPanel",
        "ReviewPanel",
        "PermissionsPanel",
        "RuntimePanel",
        "PreviewPanel",
        "LogPanel",
    ):
        assert token not in inspector_text


def test_gui_right_panel_body_has_no_inspector_tab_renderer():
    assert not (ROOT / "src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx").exists()

    checked_paths = (
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx",
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js",
    )
    for path in checked_paths:
        text = _read(path)
        for token in (
            "Inspector.jsx",
            "import Inspector",
            "<Inspector",
            "inspectorTab",
            "inspectorKind",
        ):
            assert token not in text


def test_gui_has_no_retired_workflow_runtime_panel_display_helper():
    removed_paths = (
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/workflow-display.js",
        ROOT / "src/embedagent/frontend/gui/webapp/test/workflow-display.test.mjs",
    )
    for path in removed_paths:
        assert not path.exists()

    runner_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/test/run-tests.mjs")

    for token in (
        "workflow-display",
        "runWorkflowDisplayTests",
        "inspector.currentPhase",
        "inspector.disciplineProfile",
        "inspector.currentActivity",
    ):
        assert token not in runner_text


def test_gui_has_no_split_artifact_refetch_facade():
    protocol_text = _read(ROOT / "src/embedagent/protocol/__init__.py")
    core_adapter_text = _read(ROOT / "src/embedagent/core/adapter.py")
    gui_server_text = _read(ROOT / "src/embedagent/frontend/gui/backend/server.py")
    gui_routes_text = _read(ROOT / "src/embedagent/frontend/gui/backend/routes_sessions.py")

    for token in (
        "on_artifacts_refresh",
        "artifacts_refresh",
        "_ARTIFACT_INVALIDATION",
        "/api/artifacts",
        "def list_artifacts",
        "def read_artifact",
    ):
        assert token not in protocol_text
        assert token not in core_adapter_text
        assert token not in gui_server_text
        assert token not in gui_routes_text


def test_no_hosted_or_tui_artifact_browser_facade():
    inprocess_text = _read(ROOT / "src/embedagent_host/inprocess_adapter.py")
    command_service_text = _read(ROOT / "src/embedagent_host/hosted_command_service.py")
    slash_commands_text = _read(ROOT / "src/embedagent/slash_commands.py")
    tui_app_text = _read(ROOT / "src/embedagent/frontend/tui/app.py")
    tui_controller_text = _read(ROOT / "src/embedagent/frontend/tui/controller.py")
    tui_workbench_text = _read(ROOT / "src/embedagent/frontend/tui/workbench.py")
    tui_services_init_text = _read(ROOT / "src/embedagent/frontend/tui/services/__init__.py")
    tui_services_dir = ROOT / "src/embedagent/frontend/tui/services"

    for token in (
        "def list_artifacts",
        "def read_artifact",
        "_handle_command_artifacts",
        'SlashCommandSpec("artifacts"',
        "ArtifactService",
        "artifact_service",
        "show_artifacts",
        "refresh_artifacts",
        "surface.artifacts",
        "artifact.open",
    ):
        assert token not in inprocess_text
        assert token not in command_service_text
        assert token not in slash_commands_text
        assert token not in tui_app_text
        assert token not in tui_controller_text
        assert token not in tui_workbench_text
        assert token not in tui_services_init_text

    assert not (tui_services_dir / "artifacts.py").exists()


def test_gui_manual_and_styles_do_not_keep_artifact_browser_shell():
    styles_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/styles.css")
    manual_playwright_text = _read(ROOT / "tests/manual/playwright_example.py")

    for token in (
        ".artifact-item",
        ".artifact-row",
    ):
        assert token not in styles_text

    for token in (
        "inspector-tab--",
        '"artifacts"',
    ):
        assert token not in manual_playwright_text


def test_artifact_read_model_invalidation_is_retired():
    checked_paths = (
        ROOT / "src/embedagent/tools/runtime.py",
        ROOT / "tests/test_dynamic_tool_registration.py",
    )
    offenders = []
    for path in checked_paths:
        for line_no, line in enumerate(_read(path).splitlines(), start=1):
            if (
                "read_model_invalidations" in line or "_READ_MODEL_INVALIDATIONS" in line
            ) and "artifacts" in line:
                offenders.append("%s:%s:%s" % (path.relative_to(ROOT), line_no, line.strip()))

    assert offenders == []

    tool_contracts_text = _read(ROOT / "docs/tool-contracts.md")
    development_tracker_text = _read(ROOT / "docs/development-tracker.md")
    for token in (
        "`workspace_files`, `tasks`, or `artifacts`",
        "file/task/artifact refresh",
    ):
        assert token not in tool_contracts_text
        assert token not in development_tracker_text


def test_hosted_interactions_do_not_keep_legacy_blocking_frontend_paths():
    banned_tokens = (
        "on_permission_request",
        "on_user_input_request",
        "request_permission(",
        "request_user_input(",
        "_permission_waiters",
        "_user_input_waiters",
    )
    checked_roots = (
        ROOT / "src/embedagent/protocol",
        ROOT / "src/embedagent/core",
        ROOT / "src/embedagent/frontend/gui/backend",
        ROOT / "src/embedagent/frontend/tui",
    )
    offenders = []
    for root in checked_roots:
        for path in root.rglob("*.py"):
            rel = _relative(path)
            for line_number, line in enumerate(_read(path).splitlines(), start=1):
                for token in banned_tokens:
                    if token in line:
                        offenders.append(
                            "%s:%s keeps legacy blocking interaction path %s"
                            % (rel, line_number, token)
                        )
    assert offenders == []


def test_gui_session_activity_source_state_uses_activity_vocabulary():
    checked_files = {
        "src/embedagent/frontend/gui/webapp/src/session-runtime/activity-reducer.js": (
            "action.timeline",
            "state.timeline",
            " timeline:",
            " timeline)",
            " timeline,",
            "upsertTimelineItem",
        ),
        "src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js": (
            "timeline: normalizeHistoryActivities",
        ),
        "src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js": (
            "activation.timeline",
            "timeline: activation.",
        ),
        "src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js": (
            "timeline: []",
        ),
        "src/embedagent/frontend/gui/webapp/src/store.js": (
            "action.timeline",
            "state.timeline",
            "append_timeline_item",
        ),
        "src/embedagent/frontend/gui/webapp/src/App.jsx": ("state.timeline",),
    }
    offenders = []
    for rel, forbidden_tokens in checked_files.items():
        text = _read(ROOT / rel)
        for token in forbidden_tokens:
            if token in text:
                offenders.append("%s contains source-state token %s" % (rel, token))
    assert offenders == []


def test_gui_interaction_responses_route_through_core_lifecycle():
    files = [
        ROOT / "src/embedagent/frontend/gui/backend/routes_sessions.py",
        ROOT / "src/embedagent/frontend/gui/backend/server.py",
        ROOT / "src/embedagent/frontend/gui/backend/session_events.py",
    ]
    forbidden = (
        "resolve_interaction_response",
        "_emit_interaction_resolved_event",
        "interaction_resolved",
        '"interaction.resolved"',
        "handle_permission_response",
        "handle_user_input_response",
        '"permission_response"',
        '"user_input_response"',
    )
    offenders = []
    for path in files:
        text = _read(path)
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []


def test_gui_workspace_lifecycle_stays_in_workspace_controller():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_path = (
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/workspace-controller.js"
    )
    controller_text = _read(controller_path)
    forbidden_app_tokens = (
        "async function loadAppBootstrap",
        "async function loadActiveWorkspaceData",
        "async function openWorkspace",
        "async function activateWorkspace",
        "async function removeWorkspace",
        "canSwitchWorkspace",
        "normalizeAppBootstrap",
        '"/api/app/bootstrap"',
        '"/api/app/workspaces"',
    )
    offenders = []
    for token in forbidden_app_tokens:
        if token in app_text:
            offenders.append("App.jsx owns workspace lifecycle token %s" % token)
    required_controller_tokens = (
        "export function createWorkspaceController",
        "normalizeAppBootstrap",
        '"/api/app/bootstrap"',
        '"/api/app/workspaces"',
    )
    for token in required_controller_tokens:
        if token not in controller_text:
            offenders.append("workspace-controller.js missing %s" % token)
    assert "import React" not in controller_text
    assert offenders == []


def test_gui_runtime_state_does_not_reintroduce_removed_root_session_state():
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    forbidden_root_state = (
        r"\n\s+sessions\s*:",
        r"\n\s+currentSessionId\s*:",
        r"\n\s+connectionState\s*:",
        r"\n\s+historyIntegrity\s*:",
        r"\n\s+sidebarTab\s*:",
    )
    offenders = []
    for pattern in forbidden_root_state:
        if re.search(pattern, store_text):
            offenders.append("store.js reintroduced root state %s" % pattern)
    forbidden_tokens = (
        "timeline" + "FromTurns",
        "timeline" + "FromEvents",
        "Flat" + "TimelineView",
        "set_connection",
        "set_sidebar",
        "sidebar-tab--chats",
        "activeSection",
        "projectSection",
    )
    for path in _source_files_under(
        "src/embedagent/frontend/gui/webapp/src", suffixes=(".js", ".jsx")
    ):
        rel = _relative(path)
        text = _read(path)
        for token in forbidden_tokens:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    assert not (
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/projector.js"
    ).exists()
    assert offenders == []


def test_gui_composer_state_is_thread_scoped_not_global_draft():
    composer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/composer/composer-state.js"
    )
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    assert "draftsByKey" in composer_text
    assert "draftKeyForSession" in composer_text
    assert 'draft: ""' not in store_text
