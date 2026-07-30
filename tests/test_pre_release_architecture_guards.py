from __future__ import unicode_literals

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = ROOT / "packages/embedagent-core/src/embedagent_core"
PROTOCOL_SOURCE = ROOT / "packages/embedagent-protocol/src/embedagent_protocol"
SOURCE_SUFFIXES = (".py", ".js", ".jsx")

SESSION_MUTATORS = {
    "add_system_message",
    "add_user_message",
    "begin_step",
    "record_tool_call",
    "add_assistant_reply",
    "add_observation",
    "record_transition",
    "resolve_pending_interaction",
    "record_content_replacement",
    "record_context_snapshot",
    "add_compact_boundary",
    "record_compacted_history",
}
SESSION_MUTABLE_FIELDS = {
    "messages",
    "turns",
    "pending_interaction",
    "workflow_state",
    "context_snapshots",
    "latest_context_snapshot",
    "compact_boundaries",
    "content_replacements",
    "compacted_history",
}

ACTIVE_SOURCE_FILES = [
    PROTOCOL_SOURCE / "__init__.py",
    ROOT / "packages/embedagent-host/src/embedagent_host/runtime/session_projector.py",
    ROOT / "src/embedagent/core/adapter.py",
    ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
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


def _is_chat_literal(node):
    return isinstance(node, ast.Constant) and node.value == "chat"


def _is_true_literal(node):
    return isinstance(node, ast.Constant) and node.value is True


def _dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return (prefix + "." if prefix else "") + node.attr
    return ""


def _target_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _call_name(node):
    return _target_name(node)


def _function_argument_defaults(node):
    positional = list(getattr(node.args, "posonlyargs", [])) + list(node.args.args)
    positional_with_defaults = positional[len(positional) - len(node.args.defaults) :]
    for argument, default in zip(positional_with_defaults, node.args.defaults):
        yield argument, default
    for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        if default is not None:
            yield argument, default


def _permission_policy_enables_auto_approve(node):
    if not isinstance(node, ast.Call) or _call_name(node.func) != "PermissionPolicy":
        return False
    if node.args and _is_true_literal(node.args[0]):
        return True
    for keyword in node.keywords:
        if keyword.arg == "auto_approve_all" and _is_true_literal(keyword.value):
            return True
        if keyword.arg is None and isinstance(keyword.value, ast.Dict):
            for key, value in zip(keyword.value.keys, keyword.value.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "auto_approve_all"
                    and _is_true_literal(value)
                ):
                    return True
    return False


def test_generic_host_tools_do_not_encode_legacy_workflow_states():
    source = _read(ROOT / "packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py")
    metadata_source = source.split("class ToolRuntime", 1)[0]
    visibility_lines = [
        line.strip() for line in metadata_source.splitlines() if '"workflow_visibility"' in line
    ]
    assert visibility_lines
    assert set(visibility_lines) == {'"workflow_visibility": [],'}

    fallback_source = source.split("def _build_default_metadata", 1)[1]
    assert '"workflow_visibility": [],' in fallback_source


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


def _assignment_targets(node):
    if isinstance(node, (ast.Tuple, ast.List)):
        for element in node.elts:
            for target in _assignment_targets(element):
                yield target
        return
    yield node


def test_session_reducer_is_the_only_core_session_state_writer():
    offenders = []
    for path in CORE_SOURCE.rglob("*.py"):
        if path.name == "session_reducer.py":
            continue
        tree = ast.parse(_read(path), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in SESSION_MUTATORS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "session"
            ):
                offenders.append("%s:%d calls %s" % (_relative(path), node.lineno, node.func.attr))
            assignment_nodes = []
            if isinstance(node, ast.Assign):
                assignment_nodes = list(node.targets)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                assignment_nodes = [node.target]
            for assignment in assignment_nodes:
                for target in _assignment_targets(assignment):
                    if (
                        isinstance(target, ast.Attribute)
                        and target.attr in SESSION_MUTABLE_FIELDS
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "session"
                    ):
                        offenders.append(
                            "%s:%d assigns %s" % (_relative(path), node.lineno, target.attr)
                        )
    assert offenders == []


def test_agent_loop_run_uses_one_observer_boundary_without_callback_bag():
    tree = ast.parse(
        _read(CORE_SOURCE / "agent_loop.py"),
        filename=str(CORE_SOURCE / "agent_loop.py"),
    )
    run_method = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "run"
    )
    parameter_names = {argument.arg for argument in run_method.args.args}
    assert parameter_names.isdisjoint(
        {
            "on_text_delta",
            "on_reasoning_delta",
            "on_tool_start",
            "on_tool_finish",
            "on_context_result",
            "on_step_start",
            "on_step_finish",
            "permission_handler",
            "user_input_handler",
        }
    )
    assert "observer" in parameter_names


def test_host_does_not_call_private_agent_session_methods():
    host_root = ROOT / "packages/embedagent-host/src/embedagent_host"
    offenders = []
    for path in host_root.rglob("*.py"):
        tree = ast.parse(_read(path), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                for alias in node.names:
                    qualified = module + "." + alias.name
                    if qualified in (
                        "embedagent_core.session.Session",
                        "embedagent_core.session_restore.SessionRestorer",
                    ):
                        offenders.append(
                            "%s:%d imports %s" % (_relative(path), node.lineno, qualified)
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in (
                        "embedagent_core.session",
                        "embedagent_core.session_restore",
                    ):
                        offenders.append(
                            "%s:%d imports %s module" % (_relative(path), node.lineno, alias.name)
                        )
            if isinstance(node, ast.Attribute):
                dotted = _dotted_name(node)
                if dotted.endswith("agent_session._runtime") or dotted.endswith(
                    "agent_session._submit_lock"
                ):
                    offenders.append("%s:%d accesses %s" % (_relative(path), node.lineno, dotted))
            if isinstance(node, ast.Call):
                dotted = _dotted_name(node.func)
                if ".agent_session._runtime._" in ("." + dotted):
                    offenders.append(
                        "%s:%d calls private AgentRuntime member %s"
                        % (_relative(path), node.lineno, dotted)
                    )
                if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("_host_"):
                    offenders.append(
                        "%s:%d calls private hosted method %s"
                        % (_relative(path), node.lineno, node.func.attr)
                    )
    assert offenders == []


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
        PROTOCOL_SOURCE / "__init__.py",
        ROOT / "src/embedagent/core/adapter.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
        ROOT / "src/embedagent/frontend/tui/services/timeline.py",
    ]
    offenders = []
    for path in files:
        text = _read(path)
        if "get_session" + "_timeline" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_no_core_flat_timeline_builder_name():
    text = _read(ROOT / "packages/embedagent-host/src/embedagent_host/runtime/session_history.py")
    assert "build_flat" + "_timeline" not in text


def test_no_tui_flat_or_event_history_projection_contract():
    files = [
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/session_history.py",
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
        "packages/embedagent-core/src/embedagent_core",
        "packages/embedagent-host/src/embedagent_host",
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
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
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
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/workspace_profile.py",
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
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
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
        / "packages/embedagent-protocol/src/embedagent_protocol/__init__.py": (
            "has_pending_permission:",
            "has_pending_input:",
            "pending_permission: Optional",
            "pending_input: Optional",
        ),
        ROOT
        / "packages/embedagent-host/src/embedagent_host/runtime/session_projector.py": (
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
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/session_runtime.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
        ROOT / "src/embedagent/core/adapter.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/session_projector.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/hosted_command_service.py",
        ROOT / "src/embedagent/frontend/gui/backend/server.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/services/session_lifecycle.py",
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
        PROTOCOL_SOURCE / "__init__.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py",
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


def test_session_input_does_not_own_extension_dispatch_boundary():
    text = _read(CORE_SOURCE / "session_input.py")
    assert "extension_host: AgentExtensionHost" in text
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
            offenders.append("session_input.py directly dispatches %s" % token)
    assert offenders == []


def test_public_core_has_no_chat_or_auto_approve_defaults():
    files = [
        CORE_SOURCE / "session_input.py",
        CORE_SOURCE / "turn_snapshot.py",
        CORE_SOURCE / "ports.py",
        CORE_SOURCE / "extensions.py",
        CORE_SOURCE / "agent_extension_host.py",
    ]
    workflow_names = {"workflow_state", "workflow_state_name"}
    offenders = []
    for path in files:
        tree = ast.parse(_read(path), filename=_relative(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for argument, default in _function_argument_defaults(node):
                    if argument.arg in workflow_names and _is_chat_literal(default):
                        offenders.append(
                            "%s:%s defaults %s to chat"
                            % (_relative(path), default.lineno, argument.arg)
                        )
            if isinstance(node, ast.AnnAssign):
                name = _target_name(node.target)
                if name in workflow_names and _is_chat_literal(node.value):
                    offenders.append(
                        "%s:%s defaults %s to chat" % (_relative(path), node.value.lineno, name)
                    )
            if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
                if any(_is_chat_literal(value) for value in node.values[1:]):
                    offenders.append(
                        "%s:%s uses an or-chat fallback" % (_relative(path), node.lineno)
                    )

    session_input = CORE_SOURCE / "session_input.py"
    query_tree = ast.parse(_read(session_input), filename=_relative(session_input))
    for node in ast.walk(query_tree):
        if _permission_policy_enables_auto_approve(node):
            offenders.append(
                "%s:%s enables PermissionPolicy auto approval"
                % (_relative(session_input), node.lineno)
            )

    assert offenders == []


def test_c_cpp_workflow_extension_stays_behind_default_package_boundary():
    allowed_files = set()
    allowed_prefixes = ("packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/",)
    offenders = []
    for path in _source_files_under("src/embedagent", suffixes=(".py",)):
        rel = _relative(path)
        if rel in allowed_files or rel.startswith(allowed_prefixes):
            continue
        text = _read(path)
        for token in (
            "CHarnessWorkflowExtension",
            "embedagent_workflow_cpp.extension",
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
    text = _read(ROOT / "packages/embedagent-host/src/embedagent_host/runtime/local_resources.py")
    forbidden = (
        "embedagent_workflow_cpp",
        "C_WORKFLOW_TOOL_RUN_RECIPE",
    )
    offenders = [token for token in forbidden if token in text]
    assert offenders == []


def test_self_extension_authoring_does_not_import_c_cpp_workflow_defaults():
    text = _read(
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/self_extension_authoring.py"
    )
    forbidden = (
        "embedagent_workflow_cpp",
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


def test_active_docs_use_phase7c_paths_and_vocabulary():
    active_docs = {str(_relative(path)): _read(path) for path in _active_contract_doc_files()}
    joined = "\n".join(active_docs.values())
    forbidden = (
        "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py",
        "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application_record.py",
        "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/agent_profile.py",
        "src/embedagent/agent_application_registry.py",
        "packages/embedagent-host/src/embedagent_host/runtime/agent_profile_runtime.py",
        "embedagent.workflow_packages.c_cpp",
        "AgentRuntimeServices",
        "builder_path",
        "CallbackBridge",
        "WebSocketFrontend.on_turn_event",
    )
    offenders = []
    for rel, text in active_docs.items():
        for token in forbidden:
            if token in text:
                offenders.append("%s contains %s" % (rel, token))
    assert offenders == []

    readme = active_docs["README.md"]
    architecture = active_docs["docs/overall-solution-architecture.md"]
    harness = active_docs["docs/modules/harness.md"]
    frontend_protocol = active_docs["docs/frontend-protocol.md"]
    component_path = "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/component.py"
    profile_path = "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/profile.py"

    assert component_path in readme
    assert "src/embedagent/product_catalog.py" in readme
    assert component_path in harness
    assert profile_path in harness
    assert "HostedSessionController" in architecture
    for port_name in (
        "ContextAssemblerPort",
        "SessionProjectionPort",
        "SessionRestorePolicyPort",
        "ToolRuntimePort",
    ):
        assert port_name in architecture
    assert "SessionEventEnvelope" in frontend_protocol
    assert "session_event" in frontend_protocol
    assert "SessionEventEnvelope" in joined


def test_development_tracker_uses_current_c_cpp_workflow_package_paths():
    text = _read(ROOT / "docs/development-tracker.md")

    forbidden_tokens = (
        "src/embedagent/" + "harness",
        "embedagent." + "harness",
        "src/embedagent/default_extensions.py",
        "default_extensions.py",
        "harness/workflow_projection.py",
        "harness/tool_metadata.py",
        "harness/packs.py",
    )
    offenders = [token for token in forbidden_tokens if token in text]
    assert offenders == []
    assert "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/extension.py" in text
    assert "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/application.py" in text
    assert (
        "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/workflow_projection.py"
        in text
    )
    assert "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/packs.py" in text


def test_runtime_tool_execute_calls_stay_behind_action_or_hosted_services():
    allowed_files = {
        "src/embedagent/agent_tool_action_service.py",
        "packages/embedagent-host/src/embedagent_host/hosted_command_service.py",
        "packages/embedagent-host/src/embedagent_host/runtime/review_command.py",
    }
    allowed_prefixes = ("packages/embedagent-host/src/embedagent_host/runtime/tools/",)
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
        "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/",
        "packages/embedagent-host/src/embedagent_host/runtime/tools/",
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
    runtime_reducer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js"
    )
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    diff_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/diff-surface-controller.js"
    )

    assert 'type: "diff_surface_opened"' in text
    assert 'commandName === "diff"' not in text
    assert "createDiffSurfaceController" in app_text
    assert "createDiffSurfaceState" not in app_text
    assert 'type: "diff_surface_opened"' not in app_text
    assert "createDiffSurfaceState" in diff_controller_text
    assert 'type: "diff_surface_opened"' in diff_controller_text
    assert "timelineItems" in diff_controller_text
    assert "workbenchSurfaceAllowedForApp" in runtime_reducer_text
    assert "surfaceDefinitionFor(kind, app.capabilities)" in runtime_reducer_text
    assert "bottomDrawerSurfaceDefinitionFor(kind, app.capabilities)" in runtime_reducer_text
    assert 'kind: "diff"' in runtime_reducer_text


def test_gui_command_result_session_switch_is_payload_driven():
    text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )

    assert "switch_session_id" in text
    assert 'commandName === "resume"' not in text


def test_gui_session_list_loading_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-list-controller.js"
    )

    assert "createSessionListController" in app_text
    assert "const { loadSessions } = sessionListController" in app_text
    assert "async function loadSessions" not in app_text
    assert 'fetchJson("/api/sessions")' not in app_text
    assert 'type: "sessions_loaded"' not in app_text
    assert "export function createSessionListController" in controller_text
    assert 'request("/api/sessions")' in controller_text
    assert 'type: "sessions_loaded"' in controller_text


def test_gui_session_activation_bootstrap_is_controller_handle_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js"
    )

    assert "createSessionActivationController" in app_text
    assert "const loadSession = sessionActivationController" in app_text
    assert "async function loadSession" not in app_text
    assert "deriveSessionActivation" not in app_text
    assert "export function createSessionActivationController" in controller_text
    assert 'type: "session_activated"' in controller_text
    assert 'type: "terminal_summaries_loaded"' in controller_text


def test_gui_http_client_is_runtime_owned_not_inline_app_fetch():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    http_client_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/http-client.js"
    )

    assert 'import { fetchJson } from "./app-runtime/http-client.js"' in app_text
    assert "async function fetchJson" not in app_text
    assert "fetch(" not in app_text
    assert "export function createJsonHttpClient" in http_client_text
    assert "export const { fetchJson }" in http_client_text
    assert "error.status" in http_client_text


def test_gui_initial_app_load_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/initial-app-load-controller.js"
    )

    assert "createInitialAppLoadController" in app_text
    assert "loadAppBootstrap();" not in app_text
    assert "loadSessionCommandCapabilities({ fetchJson, dispatch }).catch" not in app_text
    assert "createSessionCommandCapabilityLoader" in app_text
    assert "loadSessionCommandCapabilitiesForApp" in app_text
    assert "loadSessionCommandCapabilities({ fetchJson, dispatch })" not in app_text
    assert "export function createInitialAppLoadController" in controller_text
    assert "bootstrapResult" in controller_text
    assert "commandCapabilitiesResult" in controller_text
    assert "catch(() => null)" in controller_text


def test_gui_socket_effect_execution_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-controller.js"
    )
    executor_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-effect-executor.js"
    )

    assert "createSocketMessageController" in app_text
    assert "createSocketEffectExecutor" not in app_text
    assert "const executeSocketEffects = createSocketEffectExecutor" not in app_text
    assert "function handleSocketMessage" not in app_text
    assert "deriveSocketMessageEffects" not in app_text
    assert "appendSessionTransportEvent" not in app_text
    assert "transportEvents.length" not in app_text
    assert 'nextTransport.reloadState === "reload_required"' not in app_text
    assert "for (const action of effects.actions" not in app_text
    assert "handleMessage: socketMessageController.handleMessage" in app_text
    assert "startTransition(() => socketMessageController.handleMessage" not in app_text
    assert "handleMessage: (message) =>" not in app_text
    assert "scheduleMessage: startTransition" in app_text
    assert "export function createSocketMessageController" in controller_text
    assert "deriveSocketMessageEffects" in controller_text
    assert "createSocketEffectExecutor" in controller_text
    assert "scheduleMessage" in controller_text
    assert "function handleMessage" in controller_text
    assert "export function createSocketEffectExecutor" in executor_text
    assert "applySessionTransportEvent" in executor_text
    assert "recover(currentSessionId, nextTransport)" in executor_text
    assert "executeLoaderRequest" in executor_text


def test_gui_session_transport_state_bridge_is_handle_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    handle_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-handle.js"
    )

    assert "createSessionTransportHandle" in app_text
    assert "sessionTransportRef" not in app_text
    assert "function replaceSessionTransport" not in app_text
    assert "function updateSessionTransport" not in app_text
    assert "function createRuntimeSessionTransport" not in app_text
    assert "export function createSessionTransportHandle" in handle_text
    assert "createRuntimeTransport" in handle_text
    assert "function replace" in handle_text
    assert "function update" in handle_text
    assert "function sync" in handle_text
    assert "createSessionTransportState" in handle_text


def test_gui_responding_request_ids_bridge_is_handle_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    handle_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/responding-request-ids-handle.js"
    )

    assert "createRespondingRequestIdsHandle" in app_text
    assert "respondingRequestIdsRef" not in app_text
    assert "function setRespondingRequestIds" not in app_text
    assert "setRespondingRequestIdsState(normalized)" not in app_text
    assert "export function createRespondingRequestIdsHandle" in handle_text
    assert "normalizeRequestIds" in handle_text
    assert "function set" in handle_text
    assert "function sync" in handle_text


def test_gui_command_result_run_output_log_is_payload_driven():
    text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )

    assert "log_label" in text
    assert "log_detail" in text
    assert "logLabel" not in text
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
    adapter_text = _read(ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py")
    application_registry_text = _read(
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py"
    )
    product_registry_text = _read(ROOT / "src/embedagent/product_catalog.py")
    product_hosted_text = _read(ROOT / "src/embedagent/hosted.py")
    protocol_text = _read(PROTOCOL_SOURCE / "app_protocol.py")
    normalizer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js"
    )
    no_workspace_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/NoWorkspaceState.jsx"
    )

    assert "build_agent_application" in adapter_text
    assert "product_agent_application_registry" not in adapter_text
    assert "base_agent_application_registry" in adapter_text
    assert "product_agent_application_registry" in product_hosted_text
    assert "agentApplication" in adapter_text
    assert "agentApplications" in adapter_text
    assert "AgentApplicationRecord" in application_registry_text
    assert "AgentApplicationRegistry" in application_registry_text
    assert "BUILTIN_AGENT_APPLICATION_RECORDS" in application_registry_text
    assert "embedagent_workflow_cpp" not in application_registry_text
    assert "default_c_cpp_application_record" not in application_registry_text
    assert "default_c_cpp_application_record" in product_registry_text
    assert "DEFAULT_C_CPP_AGENT_APPLICATION_ID" in product_registry_text
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


def test_global_mode_facade_uses_generic_profile_not_default_c_cpp():
    modes_text = _read(ROOT / "src/embedagent/modes.py")

    assert "generic_agent_profile" in modes_text
    assert "default_c_cpp_agent_profile" not in modes_text
    assert "global/base agent profile" in modes_text


def test_gui_app_shell_surfaces_are_descriptor_records_not_string_lists():
    app_shell_spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    app_model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    surfaces_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js")
    right_panel_tabs_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx"
    )

    for token in (
        '_surface(\n                "files"',
        '_surface(\n                "file"',
        '_surface(\n                "terminal"',
        '"launcher_order"',
    ):
        assert token in app_shell_spec_text
    assert "surface_chrome" in app_shell_spec_text
    assert "launcher=False" in app_shell_spec_text
    assert "command=False" in app_shell_spec_text
    assert "command_label" in app_shell_spec_text
    assert "normalizeSurfaceCapability" in app_model_text
    assert "normalizeSurfaceChrome" in app_model_text
    assert "surfaceCapabilityDefinitions" in surfaces_text
    assert "surfaceChromeLabels" in surfaces_text
    assert "surfaceChromeLabels(appCapabilities)" in right_panel_tabs_text
    assert "hasDisplayTitle" in surfaces_text
    assert "&& hasDisplayTitle(definition)" in surfaces_text
    assert "label: definition.commandLabel" in surfaces_text
    assert "description: definition.description" in surfaces_text
    assert "`Open ${definition.title}`" not in surfaces_text
    assert "String(input.title || kind)" not in app_model_text
    assert (
        'return definition && definition.title ? definition.title : String(kind || "");'
        not in surfaces_text
    )
    assert '|| "file"' not in surfaces_text
    assert '|| "preview"' not in surfaces_text
    assert '|| "terminal"' not in surfaces_text
    assert "SURFACE_INITIALIZERS" in surfaces_text
    assert "SURFACE_INITIALIZERS[kind]" in surfaces_text
    for initializer_branch in (
        'kind === "file"\n      ? normalizeFilePath',
        'kind === "terminal"\n      ? uniqueTerminalIds',
        'if (kind === "preview")',
        'if (kind !== "terminal")',
    ):
        assert initializer_branch not in surfaces_text
    assert "SURFACE_OPEN_PREPARERS" in surfaces_text
    assert "SURFACE_OPEN_PREPARERS[surface.kind]" in surfaces_text
    assert "persistedRelatedKinds" in surfaces_text
    for open_branch in (
        'surface.kind === "file"\n        ? normalizeFilePath',
        'nextSurface.kind === "file"',
        'nextSurface.kind === "preview"',
    ):
        assert open_branch not in surfaces_text
    assert "SURFACE_PANE_HANDLERS" in surfaces_text
    assert "SURFACE_PANE_HANDLERS[surface.kind]" in surfaces_text
    for pane_branch in (
        'surface.id !== surfaceId || surface.kind !== "terminal"',
        'surface.kind === "terminal" &&',
        'surface.id === surfaceId && surface.kind === "terminal"',
    ):
        assert pane_branch not in surfaces_text
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
    assert "buildAppCapabilityModel" in app_text
    assert "state.app.capabilities.keybindings" not in app_text
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
    assert "buildAppCapabilityModel" in app_text
    assert "buildSessionCapabilityModelFromState" in app_text
    assert "appEmptyState || sessionEmptyState" in app_text
    assert "state.sessionCapabilities?.emptyState" not in app_text
    assert "state.sessionCapabilities?.modeCatalog" not in app_text
    assert "state.sessionCapabilities?.toolCatalog" not in app_text
    assert "stateRef.current.sessionCapabilities" not in app_text
    assert "state.app.capabilities?.emptyState" not in app_text


def test_gui_app_shell_projects_selected_agent_application_before_workspace():
    app_host_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_host.py")
    app_shell_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell.py")
    launcher_text = _read(ROOT / "src/embedagent/frontend/gui/launcher.py")
    adapter_text = _read(ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py")
    registry_text = _read(
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py"
    )

    assert "def agent_application_capability_payload" in registry_text
    assert "def agent_capabilities" in app_host_text
    assert "host_agent_capabilities" in app_shell_text
    assert "_project_agent_capabilities" in app_shell_text
    assert "agent_application_capability_payload" in launcher_text
    assert "agent_application_capability_payload" in adapter_text
    assert "available_agent_application_manifests" not in adapter_text


def test_gui_app_shell_filters_by_selected_agent_application_profile():
    app_shell_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell.py")
    registry_text = _read(
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/agent_applications.py"
    )

    assert '"appShell"' in registry_text
    assert '"rightPanelSurfaceIds"' in registry_text
    assert '"disabledCapabilityIds"' in registry_text
    assert "_selected_app_shell_profile" in app_shell_text
    assert "_apply_agent_app_shell_profile" in app_shell_text
    assert "_filter_records_by_id" in app_shell_text
    assert "_filter_keybindings" in app_shell_text
    assert '"source_control", "preview"' in registry_text
    assert "capabilities[capability_id] = disabled" in app_shell_text


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
    assert "sessionFallbackPrefix" in app_home_text
    assert "`Session ${sessionId.slice(0, 8)}`" not in app_home_text
    assert '"session_fallback_prefix": "Session"' in spec_text
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
    assert "session_leading" in spec_text
    assert "workspace_leading" in spec_text
    assert '"command_palette": {' in spec_text
    assert "def _palette_group(" in spec_text
    assert "leading=" in spec_text
    assert "normalizePaletteGroupDescriptor" in model_text
    assert "rootPlaceholder" in model_text
    assert "sessionLeading" in model_text
    assert "workspaceLeading" in model_text
    assert "shortcut_labels" in spec_text
    assert "shortcutLabels" in model_text
    assert "shortcutSeparator" in model_text
    assert "commandPalette: normalizeCommandPalette" in model_text
    assert "GROUP_TITLES" not in palette_model_text
    assert "GROUP_DESCRIPTIONS" not in palette_model_text
    assert "paletteGroupDescriptors" in palette_model_text
    assert "paletteLabels" in palette_model_text
    assert "asText(command.label) || asText(command.id)" not in palette_model_text
    assert "descriptor.description || command.id" not in palette_model_text
    assert "command.slash || command.id" not in palette_model_text
    assert "`Open ${command.surface}`" not in palette_model_text
    assert "`Open ${command.drawer}`" not in palette_model_text
    assert 'leading: "T"' not in palette_model_text
    assert 'leading: "W"' not in palette_model_text
    assert "asText(command.group) === targetGroup && asText(command.label)" in palette_model_text
    assert "title: asText(group.title) || titleCase(id)" not in palette_model_text
    assert "title: titleCase(id)" not in palette_model_text
    assert "descriptor.title || titleCase" not in palette_model_text
    assert 'return "Ctrl"' not in palette_model_text
    assert 'return "Alt"' not in palette_model_text
    assert 'return "Shift"' not in palette_model_text
    assert 'return "Esc"' not in palette_model_text
    assert "titleCase(part)" not in palette_model_text
    assert "slice(0, 1)" not in palette_model_text
    assert '|| ">"' not in palette_model_text
    assert 'asText(command.group) || "commands"' not in palette_model_text
    assert "!group || !groupDescriptor(group, groupDescriptors).title" in palette_model_text
    assert "if (!title) return []" in palette_model_text
    assert '"Command palette"' not in palette_component_text
    assert '"Search commands, sessions, workspaces"' not in palette_component_text
    assert '"No matching commands, sessions, or workspaces"' not in palette_component_text
    assert '"No matching commands, sessions, or workspaces"' not in palette_results_text
    assert 'item.leading || ">"' not in palette_results_text
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
    surface_panel_props_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/surface-panel-props.js"
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
    assert "buildAppCapabilityModel" in app_text
    assert "appChrome" in app_text
    assert "chrome={appChrome.header || {}}" in app_text
    assert "chrome={appChrome}" in app_text
    assert "chrome={appChrome.composer || {}}" in app_text
    assert "interactionChrome={appChrome.interaction || {}}" in app_text
    assert "chrome: appChrome.surfacePanel || {}" not in app_text
    assert "chrome: appChrome.surfacePanel || {}" in surface_panel_props_text
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
    assert "interactionChrome = {}" in composer_text
    assert "chrome={interactionChrome}" in composer_text
    assert "chrome={chrome.interaction || {}}" not in composer_text
    assert "hintLabels[hint.id]" not in composer_text
    assert "hint.label || hint.id" in composer_text
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


def test_gui_composer_hints_are_app_shell_descriptors():
    spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")
    model_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-shell/model.js")
    composer_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Composer.jsx")
    interaction_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/composer/composer-interaction-model.js"
    )

    assert '"hints": [' in spec_text
    assert '"visible_when": "always"' in spec_text
    assert '"visible_when": "running"' in spec_text
    assert "normalizeComposerHints" in model_text
    assert "visibleWhen" in model_text
    assert "hintDescriptors" in composer_text
    assert "hint.label || hint.id" in composer_text
    assert "hintDescriptors" in interaction_model_text
    assert 'id: "command"' not in interaction_model_text
    assert 'id: "file"' not in interaction_model_text
    assert '"status.running"' not in interaction_model_text


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
    assert '"default_command_group_id": "command"' in spec_text
    assert "normalizeComposerCommandMenuChrome" in model_text
    assert "commandMenu: normalizeComposerCommandMenuChrome" in model_text
    assert "defaultCommandGroupId" in model_text
    assert "composerCommandGroupLabels" in app_text
    assert "buildCommandGroupLabels" in app_text
    assert "commandPaletteGroups.reduce" not in app_text
    assert "group?.id) labels[group.id]" not in app_text
    assert "commandGroupLabels={composerCommandGroupLabels}" in app_text
    assert "const commandMenuChrome = chrome.commandMenu || {}" in composer_text
    assert "commandGroupLabels" in composer_text
    assert "chrome={commandMenuChrome}" in composer_text
    assert "chrome.pathAriaLabel" in menu_text
    assert "chrome.pathItemKindLabel" in menu_text
    assert "commandMenuChrome.pathGroupLabel" in path_context_text
    assert "commandMenuChrome.commandEmptyText" in interaction_model_text
    assert "commandGroupLabels" in command_search_text
    assert "defaultCommandGroupId" in command_search_text
    assert "GROUP_LABELS" not in command_search_text

    command_capabilities_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/command-capabilities.js"
    )
    workbench_commands_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/commands.js"
    )
    protocol_normalizer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js"
    )
    for source_text in (
        command_capabilities_text,
        command_search_text,
        workbench_commands_text,
        protocol_normalizer_text,
    ):
        assert '|| "command"' not in source_text
    assert 'group: "command"' not in command_capabilities_text

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


def test_gui_composer_slash_menu_does_not_keep_static_hint_fallbacks():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    composer_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/components/Composer.jsx")
    interaction_model_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/composer/composer-interaction-model.js"
    )

    assert "EMPTY_COMMAND_HINTS" not in app_text
    assert "commandHints" not in app_text
    assert "commandHints" not in composer_text
    assert "commandsFromHints" not in interaction_model_text
    assert "commandHints" not in interaction_model_text
    assert 'group: "command"' not in interaction_model_text


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
    activation_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js"
    )
    terminal_capability_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/terminal/terminal-capability.js"
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
    assert "terminalCapabilityEnabled" in controller_text
    assert "../terminal/terminal-capability.js" in controller_text
    assert "terminalCapabilityEnabled" in activation_controller_text
    assert "appCapabilities?.terminal?.enabled === true" not in controller_text
    assert "capabilities?.terminal?.enabled === true" in terminal_capability_text
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
    preview_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/preview-controller.js"
    )
    surface_body_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx"
    )

    assert '"preview": _copy_value(self.preview)' in spec_text
    assert '"session_required_notice": "Open a session before using preview."' in spec_text
    assert "normalizePreviewChrome" in model_text
    assert "preview: normalizePreviewCapability" in model_text
    assert "createPreviewController" in app_text
    assert "onPreviewOpenUrl={previewController.openUrl}" in app_text
    assert "onPreviewRefresh={previewController.refresh}" in app_text
    assert "onPreviewOpenExternal={previewController.openExternal}" in app_text
    assert "async function openPreviewUrl" not in app_text
    assert "async function refreshPreview" not in app_text
    assert "async function openPreviewInSystemBrowser" not in app_text
    assert "previewChrome.sessionRequiredNotice" not in app_text
    assert "chrome.sessionRequiredNotice" in preview_controller_text
    assert "chrome.failedNotice" in preview_controller_text
    assert "chrome.refreshFailedNotice" in preview_controller_text
    assert "chrome.openFailedNotice" in preview_controller_text
    assert "previewCapability.localServers" not in app_text
    assert "previewChrome={previewChrome}" in app_text
    assert "previewServers={previewServers}" in app_text
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
    file_preview_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/file-preview-controller.js"
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
    assert '"breadcrumb_aria_label": "File path"' in spec_text
    assert '"markdown_source_glyph": "C"' in spec_text
    assert '"markdown_preview_glyph": "P"' in spec_text
    assert "normalizeFilePreviewChrome" in model_text
    assert "filePreview: normalizeFilePreviewChrome" in model_text
    assert "createFilePreviewController" in app_text
    assert "onOpenFile={filePreviewController.openFile}" in app_text
    assert "async function openFile" not in app_text
    assert "filePreviewController.openFile(path, line)" not in app_text
    assert "function openDiffSurface" not in app_text
    assert "async function openPreviewUrl" not in app_text
    assert "async function refreshPreview" not in app_text
    assert "async function openPreviewInSystemBrowser" not in app_text
    assert "filePreviewChrome.unavailableMessage" not in app_text
    assert "filePreviewChrome.unavailableMessage" not in file_preview_controller_text
    assert "chrome.unavailableMessage" in file_preview_controller_text
    assert "fileSurfaceTitle(filePath, filePreviewChrome)" not in app_text
    assert "/api/files/" in file_preview_controller_text
    assert "file_preview_load_started" in file_preview_controller_text
    assert "file_preview_loaded" in file_preview_controller_text
    assert "file_preview_load_failed" in file_preview_controller_text
    assert "fileSurfaceTitle(path, filePreviewChrome" in right_panel_controller_text
    assert 'replace(/^Open\\s+/i, "")' not in right_panel_controller_text
    assert "filePreviewChrome={filePreviewChrome}" in surface_body_text
    assert "filePreviewChrome" in file_preview_surface_text
    assert "filePreviewChrome.breadcrumbAriaLabel" in file_preview_surface_text
    assert "filePreviewChrome.markdownSourceGlyph" in file_preview_surface_text
    assert "filePreviewChrome.markdownPreviewGlyph" in file_preview_surface_text
    assert "chrome.languageLabels" in file_preview_model_text

    for hardcoded_copy in (
        '"File unavailable"',
        '"Loading file..."',
        ">Retry<",
        '"Show markdown source"',
        '"Show rendered markdown"',
        '"Show file explorer"',
        '"File path"',
        '{showPreview ? "C" : "P"}',
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
    source_control_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/source-control-controller.js"
    )
    source_control_capability_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/source-control/source-control-capability.js"
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
    assert '"file_status_labels": {' in spec_text
    assert '"group_order": [' in spec_text
    assert "normalizeSourceControlChrome" in model_text
    assert "chrome: normalizeSourceControlChrome" in model_text
    assert "groupOrder:" in model_text
    assert "fileStatusLabels: normalizeStringMap" in model_text
    assert "branchToolbar: normalizeBranchToolbarChrome" in model_text
    assert "createSourceControlController" in app_text
    assert "sourceControlChrome.statusUnavailableNotice" in source_control_controller_text
    assert "sourceControlChrome.diffUnavailableNotice" in source_control_controller_text
    assert "sourceControlChrome" in app_text
    assert "sourceControlCapabilityEnabled" not in app_text
    assert "sourceControlCapabilityEnabled" in source_control_controller_text
    assert "!sourceControlCapabilityEnabled(stateRef.current.app.capabilities)" not in app_text
    assert "sourceControl.enabled === true" in source_control_capability_text
    assert "sourceControlChrome" in surface_panel_text
    assert "sourceControlChrome" in source_control_panel_text
    assert "sourceControlChrome.groupOrder" in source_control_panel_text
    assert '["conflicted", "staged", "unstaged", "untracked"]' not in source_control_panel_text
    assert "chrome.groupLabels" in source_control_presentation_text
    assert "chrome.providerLabels" in source_control_presentation_text
    assert "chrome.fileStatusLabels" in source_control_presentation_text
    assert "slice(0, 1)" not in source_control_presentation_text
    assert '"?"' not in source_control_presentation_text
    assert "|| normalized" not in source_control_presentation_text
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
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    app_home_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/app-home-model.js"
    )
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/thread-lifecycle-controller.js"
    )
    browser_dialog_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/browser-dialog-service.js"
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
    assert "createBrowserDialogService" in app_text
    assert "prompt: browserDialogService.prompt" in app_text
    assert "confirm: browserDialogService.confirm" in app_text
    assert "window.prompt" not in app_text
    assert "window.confirm" not in app_text
    assert "export function createBrowserDialogService" in browser_dialog_text
    assert "target.prompt" in browser_dialog_text
    assert "target.confirm" in browser_dialog_text
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
    extensions_text = _read(CORE_SOURCE / "extensions.py")
    turn_experience_text = _read(CORE_SOURCE / "turn_experience.py")

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
    protocol_text = _read(PROTOCOL_SOURCE / "__init__.py")
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
    protocol_text = _read(PROTOCOL_SOURCE / "__init__.py")
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
    protocol_text = _read(PROTOCOL_SOURCE / "__init__.py")
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
    runtime_reducer_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/client-runtime/runtime-reducer.js"
    )
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
    terminal_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js"
    )
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-command-controller.js"
    )
    app_shell_spec_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py")

    assert "appCapabilities" in commands_text
    assert "surfaceCommandDefinitions(appCapabilities)" in commands_text
    assert "bottomDrawerCommandDefinitions(appCapabilities)" in commands_text
    assert "if (declared === null) return commands" not in commands_text
    assert "sanitizeWorkbenchUiStateForAppCapabilities" in runtime_reducer_text
    assert "sanitizeWorkbenchUiStateForAppCapabilities" in ui_state_text
    assert "persistedSurfaceDefinitions(appCapabilities, placement)" in ui_state_text
    assert "persistedSurfaceFrom" in ui_state_text
    assert 'kind === "file"' not in ui_state_text
    assert 'kind === "terminal"' not in ui_state_text
    assert 'kind !== "terminal"' not in ui_state_text
    assert "persistedSurfaceDefinitions" in ui_state_text
    assert 'kinds.includes("files")' not in ui_state_text
    assert 'kinds.concat("file")' not in ui_state_text
    assert "appCapabilities" in keybindings_text
    assert "rightPanelLauncherSurfaceDefinitions(appCapabilities)" in right_panel_tabs_text
    assert "bottomDrawerSurfaceDefinitions(appCapabilities)" in bottom_drawer_text
    assert "surfaceChromeLabels" in bottom_drawer_text
    assert "chrome.bottomDrawerAriaLabel" in bottom_drawer_text
    assert "chrome.runOutputEmptyMessage" in bottom_drawer_text
    assert "chrome.terminationReasonPrefix" in bottom_drawer_text
    assert "activeDefinition.bodyKind" in bottom_drawer_text
    assert "BOTTOM_DRAWER_BODY_RENDERERS" in bottom_drawer_text
    assert "BOTTOM_DRAWER_BODY_RENDERERS[activeBodyKind]" in bottom_drawer_text
    assert "switch (activeBodyKind)" not in bottom_drawer_text
    assert "bottomDrawerSurfaceDefinitionFor" in terminal_controller_text
    assert "TERMINAL_SURFACE_KIND" in terminal_controller_text
    assert "terminalSurfaceActionInput" in terminal_controller_text
    assert "definition.activationKind" in terminal_controller_text
    assert "BOTTOM_DRAWER_ACTIVATION_HANDLERS" in terminal_controller_text
    assert (
        "BOTTOM_DRAWER_ACTIVATION_HANDLERS[definition.activationKind]" in terminal_controller_text
    )
    assert "defaultNextTerminalId" in terminal_controller_text
    assert "openNewBottomDrawerTerminal" in terminal_controller_text
    assert "activateBottomDrawerTerminal" in terminal_controller_text
    assert "onKindSelect={terminalController.selectBottomDrawerKind}" in app_text
    assert "onTerminalNew={terminalController.openNewBottomDrawerTerminal}" in app_text
    assert "onTerminalSelect={terminalController.activateBottomDrawerTerminal}" in app_text
    assert "terminalController.ensureOpen" not in app_text
    assert "nextTerminalId" not in app_text
    assert 'type: "terminal_active_set"' not in app_text
    assert "onTerminalNew={terminalController.openRightPanelSurface}" in app_text
    assert "onTerminalSplit={terminalController.splitActiveRightPanelSurface}" in app_text
    assert (
        "onTerminalSplitVertical={terminalController.splitActiveRightPanelSurfaceVertical}"
        in app_text
    )
    assert "onTerminalSelect={terminalController.activateActiveRightPanelPane}" in app_text
    assert "onTerminalClose={terminalController.closeActiveRightPanelPane}" in app_text
    assert "terminalController.splitRightPanelSurface" not in app_text
    assert "terminalController.closeRightPanelPane" not in app_text
    assert "terminalController.activateRightPanelPane" not in app_text
    assert "activeRightPanelSurface, terminalId" not in app_text
    assert "activeRightPanelSurfaceFrom(state.workbench)" in app_text
    assert "rightPanelSurfacesFrom(state.workbench)" in app_text
    assert "rightPanelSurfaces.find" not in app_text
    assert "surface.id === state.workbench.rightPanel.activeSurfaceId" not in app_text
    assert "function activeRightPanelSurface" not in terminal_controller_text
    assert "activeRightPanelSurfaceFrom" in terminal_controller_text
    assert "function splitActiveRightPanelSurface" in terminal_controller_text
    assert "function splitActiveRightPanelSurfaceVertical" in terminal_controller_text
    assert "function activateActiveRightPanelPane" in terminal_controller_text
    assert "function closeActiveRightPanelPane" in terminal_controller_text
    assert "commandById" not in app_text
    assert "onToggleRightPanel={workbenchCommandController.toggleRightPanel}" in app_text
    assert "onToggleBottomDrawer={workbenchCommandController.toggleBottomDrawer}" in app_text
    assert "onOpenPalette={workbenchCommandController.openPalette}" in app_text
    assert "onQueryChange={workbenchCommandController.updatePaletteQuery}" in app_text
    assert "onClose={workbenchCommandController.closePalette}" in app_text
    assert "onSelect={workbenchCommandController.selectPaletteCommand}" in app_text
    assert "onSelectSession={workbenchCommandController.selectPaletteSession}" in app_text
    assert "onSelectWorkspace={workbenchCommandController.selectPaletteWorkspace}" in app_text
    assert 'type: "workbench_command_palette_closed"' not in app_text
    assert 'type: "workbench_command_palette_query_changed"' not in app_text
    assert 'type: "workbench_right_panel_toggled"' not in app_text
    assert 'type: "workbench_bottom_drawer_toggled"' not in app_text
    assert "commandById" in controller_text
    assert "function openPalette" in controller_text
    assert "function closePalette" in controller_text
    assert "function updatePaletteQuery" in controller_text
    assert "function toggleRightPanel" in controller_text
    assert "function toggleBottomDrawer" in controller_text
    assert "function selectPaletteCommand" in controller_text
    assert "function selectPaletteSession" in controller_text
    assert "function selectPaletteWorkspace" in controller_text
    assert 'switch (definition ? definition.activationKind : "")' not in terminal_controller_text
    assert 'kind === "terminal"' not in terminal_controller_text
    assert 'surface.kind !== "terminal"' not in terminal_controller_text
    assert 'surfaceDefinitionFor("terminal"' not in terminal_controller_text
    assert 'activeKind === "terminal"' not in bottom_drawer_text
    assert '"Bottom drawer"' not in bottom_drawer_text
    assert '"No run output yet."' not in bottom_drawer_text
    assert "reason={terminationReason}" not in bottom_drawer_text
    assert '_dispatch("command_palette.open")' in app_shell_spec_text
    assert '_dispatch("workspace.focus_path_input")' in app_shell_spec_text
    assert '_dispatch("session.create")' in app_shell_spec_text
    assert '_dispatch("terminal.ensure_open")' in app_shell_spec_text
    assert '_surface(\n                "logs",' not in app_shell_spec_text
    assert "command.dispatch" in controller_text
    assert "COMMAND_DISPATCH_HANDLERS" in controller_text
    assert "COMMAND_DISPATCH_HANDLERS[dispatchDescriptor.kind]" in controller_text
    assert "switch (dispatchDescriptor.kind)" not in controller_text
    assert 'case "terminal.ensure_open"' not in controller_text
    assert "switch (command.id)" not in controller_text
    assert 'command.drawer === "terminal"' not in controller_text
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
        'case "app.reload"',
        'case "palette.open"',
        'case "workspace.open"',
        'case "session.new"',
        'case "message.send"',
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


def test_gui_visual_debug_installation_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-controller.js"
    )
    fixtures_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js"
    )

    assert "createVisualDebugController" in app_text
    assert "installVisualDebugFixtures" not in app_text
    assert "__EMBEDAGENT_VISUAL_DEBUG__" not in app_text
    assert "window.location.search" not in app_text
    assert "export function createVisualDebugController" in controller_text
    assert "installVisualDebugFixtures" in controller_text
    assert "getLocationSearch" in controller_text
    assert "getCurrentMode" in controller_text
    assert "export function installVisualDebugFixtures" in fixtures_text


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
    surface_body_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelSurfaceBody.jsx"
    )
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    surfaces_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js")
    surface_panel_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )
    assert "surfaceDefinitionFor(surface.kind, appCapabilities)" in surface_body_text
    assert "surfaceDefinitionFor(surface.kind)" not in surface_body_text
    assert "buildAppCapabilityModelFromState" in app_text
    assert "state.app.capabilities" not in app_text
    assert "stateRef.current.app.capabilities" not in app_text
    assert app_text.count("appCapabilities={appCapabilities}") >= 3
    assert "activeDefinition.bodyKind" in surface_body_text
    assert "activeDefinition.panelKind" in surface_body_text
    assert "RIGHT_PANEL_BODY_RENDERERS" in surface_body_text
    assert "RIGHT_PANEL_BODY_RENDERERS[activeBodyKind]" in surface_body_text
    assert "switch (activeBodyKind)" not in surface_body_text
    assert "bodyKind" in surfaces_text
    assert "panelKind" in surfaces_text
    assert "PANEL_RENDERERS" in surface_panel_text
    assert "panelKind" in surface_panel_text
    for token in (
        'surface.kind === "file"',
        'surface.kind === "files"',
        'surface.kind === "preview"',
        'surface.kind === "terminal"',
    ):
        assert token not in surface_body_text
    for token in (
        'surfaceKind === "plan"',
        'surfaceKind === "diff"',
        'surfaceKind === "source_control"',
        'surfaceKind === "settings"',
        'surfaceKind === "diagnostics"',
    ):
        assert token not in surface_panel_text


def test_gui_right_panel_open_behavior_is_surface_metadata_driven():
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js"
    )
    terminal_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/terminal-controller.js"
    )
    file_preview_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/file-preview-controller.js"
    )
    preview_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/preview-controller.js"
    )
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    surfaces_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js")

    assert "declaredRightPanelSurfaceDefinition" in controller_text
    assert "surfaceDefinitionFor(kind, capabilities)" in controller_text
    assert "definition.openKind" in controller_text
    assert "RIGHT_PANEL_OPEN_HANDLERS" in controller_text
    assert "RIGHT_PANEL_OPEN_HANDLERS[definition.openKind]" in controller_text
    assert 'switch (definition ? definition.openKind : "")' not in controller_text
    assert "RIGHT_PANEL_ACTIVATION_HANDLERS" in controller_text
    assert "RIGHT_PANEL_ACTIVATION_HANDLERS[definition.activationKind]" in controller_text
    assert "onActivateSurface={rightPanelController.activateSurface}" in app_text
    assert "onCloseSurface={rightPanelController.closeSurface}" in app_text
    assert "onCloseOtherSurfaces={rightPanelController.closeOtherSurfaces}" in app_text
    assert "onCloseSurfacesToRight={rightPanelController.closeSurfacesToRight}" in app_text
    assert "onCloseAllSurfaces={rightPanelController.closeAllSurfaces}" in app_text
    assert "onAddSurface={openRightPanelSurface}" in app_text
    assert 'type: "workbench_surface_closed"' not in app_text
    assert 'type: "workbench_surface_close_others"' not in app_text
    assert 'type: "workbench_surface_close_to_right"' not in app_text
    assert 'type: "workbench_surface_close_all"' not in app_text
    assert "definition.activationKind" not in app_text
    assert 'definition.activationKind === "terminal.open_active"' not in app_text
    assert "surfaceDefinitionFor(" not in app_text
    assert 'kind: "file"' not in app_text
    assert 'kind: "preview"' not in app_text
    assert 'openRightPanelSurface("files")' not in app_text
    assert "createFilePreviewController" in app_text
    assert "rightPanelController.openFileSurface(" not in app_text
    assert "const opened = rightPanelController.openFileSurface(" not in app_text
    assert "if (!opened) return;" not in app_text
    assert "openSurface({" in file_preview_controller_text
    assert "if (!opened) return null;" in file_preview_controller_text
    assert "createPreviewController" in app_text
    assert "rightPanelController.openPreviewSurface(" not in app_text
    assert "rightPanelController.canOpenPreviewSurface()" not in app_text
    assert "canOpenPreviewSurface" in preview_controller_text
    assert "openPreviewSurface" in preview_controller_text
    assert "onOpenFilesSurface={rightPanelController.openFilesSurface}" in app_text
    assert "openKind" in surfaces_text
    assert "activationKind" in surfaces_text
    assert "RIGHT_PANEL_RESOURCE_SURFACES.file" in controller_text
    assert "RIGHT_PANEL_RESOURCE_SURFACES.preview" in controller_text
    assert "terminalController.openRightPanelSurface" in controller_text
    assert "terminalController.openSession" in controller_text
    assert "rightPanelTerminalSurfaceDefinition" in terminal_controller_text
    assert "if (!definition) return null" in terminal_controller_text
    assert "return false" in controller_text
    assert "return true" in controller_text
    assert "openFileSurface" in controller_text
    assert "canOpenPreviewSurface" in controller_text
    assert "openPreviewSurface" in controller_text
    assert "openFilesSurface" in controller_text
    assert "function closeSurface" in controller_text
    assert "function closeOtherSurfaces" in controller_text
    assert "function closeSurfacesToRight" in controller_text
    assert "function closeAllSurfaces" in controller_text
    assert 'type: "workbench_surface_closed"' in controller_text
    assert 'type: "workbench_surface_close_others"' in controller_text
    assert 'type: "workbench_surface_close_to_right"' in controller_text
    assert 'type: "workbench_surface_close_all"' in controller_text
    assert "terminalController.openSession" not in app_text
    for token in (
        'surfaceKind === "file"',
        'surfaceKind === "terminal"',
    ):
        assert token not in controller_text
    assert 'surface.kind === "terminal"' not in app_text


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
    protocol_text = _read(PROTOCOL_SOURCE / "__init__.py")
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
    inprocess_text = _read(
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py"
    )
    command_service_text = _read(
        ROOT / "packages/embedagent-host/src/embedagent_host/hosted_command_service.py"
    )
    slash_commands_text = _read(
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/slash_commands.py"
    )
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
        ROOT / "packages/embedagent-host/src/embedagent_host/runtime/tools/runtime.py",
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
        PROTOCOL_SOURCE,
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


def test_renderer_has_one_agent_event_transport_path():
    source = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js"
    )

    assert 'type === "session_event"' in source
    for legacy_type in (
        "tool_start",
        "tool_finish",
        "command_result",
        "session_status",
        "stream_delta",
        "reasoning_delta",
        "session_finished",
    ):
        assert 'type === "%s"' % legacy_type not in source


def test_renderer_transport_uses_canonical_envelope_ordering_fields():
    source = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js"
    )

    assert "event.sequence" in source
    assert re.search(r"event\.seq(?!uence)", source) is None
    assert "event.schema_version" in source
    assert "event.timestamp" in source


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
        "workspace_path_changed",
        '"/api/app/bootstrap"',
        '"/api/app/workspaces"',
    )
    offenders = []
    for token in forbidden_app_tokens:
        if token in app_text:
            offenders.append("App.jsx owns workspace lifecycle token %s" % token)
    required_controller_tokens = (
        "export function createWorkspaceController",
        "function setWorkspacePath",
        'type: "workspace_path_changed"',
        "normalizeAppBootstrap",
        '"/api/app/bootstrap"',
        '"/api/app/workspaces"',
    )
    for token in required_controller_tokens:
        if token not in controller_text:
            offenders.append("workspace-controller.js missing %s" % token)
    assert "onWorkspacePathChange={setWorkspacePath}" in app_text
    assert "onChange={setWorkspacePath}" in app_text
    assert "import React" not in controller_text
    assert offenders == []


def test_gui_active_workspace_data_loading_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    loader_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/active-workspace-data-loader.js"
    )

    assert "createActiveWorkspaceDataLoader" in app_text
    assert "loadWorkspaceData: activeWorkspaceDataLoader.loadActiveWorkspaceData" in app_text
    assert "Promise.all([" not in app_text
    assert 'loadFileChildren(".", { appCapabilities' not in app_text
    assert "sourceControlController.loadStatus(false, assumeWorkspace" not in app_text
    assert "loadStatus: sourceControlController.loadStatus" in app_text
    assert "loadStatus: (refresh, assumeWorkspace, appCapabilities)" not in app_text
    assert (
        "sourceControlController.loadStatus(refresh, assumeWorkspace, appCapabilities)"
        not in app_text
    )
    assert "export function createActiveWorkspaceDataLoader" in loader_text
    assert "Promise.all([" in loader_text
    assert 'invoke(loadFileChildren, ".",' in loader_text
    assert "invoke(loadStatus, false," in loader_text


def test_gui_composer_actions_are_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/composer-controller.js"
    )

    assert "createComposerController" in app_text
    assert "function sendMessage" not in app_text
    assert "onChange={composerController.setDraft}" in app_text
    assert "onSend={composerController.sendMessage}" in app_text
    assert "onOpenCommandPalette={composerController.openCommandPalette}" in app_text
    assert "onRefreshSourceControl={composerController.refreshSourceControl}" in app_text
    assert "export function createComposerController" in controller_text
    assert 'type: "set_composer"' in controller_text
    assert 'type: "workbench_command_palette_opened"' in controller_text
    assert "refreshSourceControl" in controller_text
    assert "import React" not in controller_text


def test_gui_surface_panel_actions_are_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/surface-panel-controller.js"
    )
    props_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/surface-panel-props.js"
    )

    assert "createSurfacePanelController" in app_text
    assert "buildSurfacePanelProps" in app_text
    assert "surfacePanelController.focusDiffFile" not in app_text
    assert "surfacePanelController.refreshSourceControl" not in app_text
    assert "surfacePanelController.selectSourceControlFile" not in app_text
    assert "surfacePanelController.changeAppSettings" not in app_text
    assert "onFocusDiffFile: surfacePanelController.focusDiffFile" not in app_text
    assert "onRefreshSourceControl: surfacePanelController.refreshSourceControl" not in app_text
    assert (
        "onSelectSourceControlFile: surfacePanelController.selectSourceControlFile" not in app_text
    )
    assert "onAppSettingsChange: surfacePanelController.changeAppSettings" not in app_text
    assert "diff_file_focused" not in app_text
    assert "app_shell_settings_changed" not in app_text
    assert "sourceControlController.loadStatus(true)" not in app_text
    assert "sourceControlController.openFile(file, scope)" not in app_text
    assert "export function createSurfacePanelController" in controller_text
    assert "function focusDiffFile" in controller_text
    assert "function refreshSourceControl" in controller_text
    assert "function selectSourceControlFile" in controller_text
    assert "function changeAppSettings" in controller_text
    assert 'type: "diff_file_focused"' in controller_text
    assert 'type: "app_shell_settings_changed"' in controller_text
    assert "import React" not in controller_text
    assert "export function buildSurfacePanelProps" in props_text
    assert "onFocusDiffFile: controller.focusDiffFile" in props_text
    assert "onRefreshSourceControl: controller.refreshSourceControl" in props_text
    assert "onSelectSourceControlFile: controller.selectSourceControlFile" in props_text
    assert "onAppSettingsChange: controller.changeAppSettings" in props_text
    assert "import React" not in props_text


def test_gui_panel_resize_dom_logic_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/panel-resize-controller.js"
    )

    assert "createPanelResizeController" in app_text
    assert "onResizeSidebar={panelResizeController.startSidebarResize}" in app_text
    assert "onResizeRightPanel={panelResizeController.startRightPanelResize}" in app_text
    assert "panelResizeController.startResize" not in app_text
    assert "RESIZE_DIRECTIONS" not in app_text
    assert "function startResize" not in app_text
    assert "setPointerCapture" not in app_text
    assert "document.documentElement.style.setProperty" not in app_text
    assert "getComputedStyle(document.documentElement)" not in app_text
    assert "export function createPanelResizeController" in controller_text
    assert "function startSidebarResize" in controller_text
    assert "function startRightPanelResize" in controller_text
    assert "return { startResize" not in controller_text
    assert "export const RESIZE_DIRECTIONS" not in controller_text
    assert "RESIZE_DIRECTIONS" in controller_text
    assert "setPointerCapture" in controller_text
    assert "documentRef.documentElement.style.setProperty" in controller_text


def test_gui_timeline_scroll_dom_logic_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/timeline-scroll-controller.js"
    )

    assert "createTimelineScrollController" in app_text
    assert "timelineScrollController.syncToBottom()" in app_text
    assert "onScroll={timelineScrollController.handleScroll}" in app_text
    assert "function handleTimelineScroll" not in app_text
    assert "isAtBottomRef" not in app_text
    assert "scrollTop" not in app_text
    assert "scrollHeight" not in app_text
    assert "clientHeight" not in app_text
    assert "export function createTimelineScrollController" in controller_text
    assert "scrollTop" in controller_text
    assert "scrollHeight" in controller_text
    assert "clientHeight" in controller_text


def test_gui_interaction_response_bridge_does_not_keep_root_forwarders():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js"
    )

    assert "createInteractionResponseController" in app_text
    assert "function logEvent" not in app_text
    assert "logEvent:" not in app_text
    assert "function respondToInteraction" not in app_text
    assert "onRespondInteraction={interactionResponseController.respondToInteraction}" in app_text
    assert "logEvent" not in controller_text
    assert 'type: "log_event"' in controller_text


def test_gui_workbench_keyboard_handling_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/workbench-keyboard-controller.js"
    )
    commands_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/commands.js")
    parity_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/workbench/workbench-parity-model.js"
    )

    assert "createWorkbenchKeyboardController" in app_text
    assert "buildCommandVisibilityContext" in app_text
    assert "function isTurnInterruptibleStatus" not in app_text
    assert "hasSession: Boolean(currentSessionId)" not in app_text
    assert "paletteOpen: state.workbench.commandPalette.open" not in app_text
    assert "paletteOpen: current.workbench.commandPalette.open" not in app_text
    assert "isRunning: isTurnInterruptibleStatus(status)" not in app_text
    assert "workbenchKeyboardController.install()" in app_text
    assert "function onWorkbenchKeyDown" not in app_text
    assert 'window.addEventListener("keydown"' not in app_text
    assert 'window.removeEventListener("keydown"' not in app_text
    assert "document.activeElement?.dataset?.testid" not in app_text
    assert "resolveKeybinding(" not in app_text
    assert "eventToKey(" not in app_text
    assert "export function createWorkbenchKeyboardController" in controller_text
    assert 'addEventListener("keydown"' in controller_text
    assert "resolveKeybinding" in controller_text
    assert "eventToKey" in controller_text
    assert "composerFocused" in controller_text
    assert "export function buildCommandVisibilityContext" in commands_text
    assert "export function isTurnInterruptibleStatus" in commands_text
    assert "function isRunningStatus" not in parity_text
    assert "buildAppCapabilityModelFromState" in parity_text
    assert "buildSessionCapabilityModelFromState" in parity_text
    assert "state.app.capabilities" not in parity_text
    assert "state.sessionCapabilities" not in parity_text


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


def test_session_reducer_is_closed_internal_dispatch():
    source = _read(CORE_SOURCE / "session_reducer.py")
    core_root_source = _read(CORE_SOURCE / "__init__.py")
    assert "def register" not in source
    assert "SessionReducer" not in core_root_source
