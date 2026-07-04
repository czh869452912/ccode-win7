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


def test_agent_core_has_no_harness_prompt_or_command_name_validation_coupling():
    extensions_text = _read(ROOT / "src/embedagent_core/extensions.py")
    turn_experience_text = _read(ROOT / "src/embedagent_core/turn_experience.py")

    assert "HarnessPrompt" not in extensions_text
    assert "_looks_like_validation" not in turn_experience_text
    for command_marker in ("ctest", "ninja", "cmake", "clang", "gcc"):
        assert command_marker not in turn_experience_text


def test_gui_workflow_display_and_default_mode_are_backend_declared():
    workflow_display_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/workflow-display.js"
    )
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

    for token in (
        "snapshot.current_phase",
        "snapshot.discipline_profile",
        "workflow.current_phase",
        "workflow.discipline_profile",
    ):
        assert token not in workflow_display_text
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
    inspector_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx")
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
    commands_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/commands.js")
    keybindings_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/keybindings.js"
    )
    inspector_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx")
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
    assert "appCapabilities" in keybindings_text
    assert "rightPanelLauncherSurfaceDefinitions(appCapabilities)" in right_panel_tabs_text
    assert "bottomDrawerSurfaceDefinitions(appCapabilities)" in bottom_drawer_text
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
