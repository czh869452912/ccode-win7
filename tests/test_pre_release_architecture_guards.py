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
    ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
    ROOT / "src/embedagent/frontend/gui/backend/server.py",
    ROOT / "src/embedagent/frontend/gui/webapp/src/state-helpers.js",
    ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx",
    ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-message-effects.js",
    ROOT / "src/embedagent/frontend/runtime/session_client_runtime.py",
    ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/activity-state.js",
]


def _read(path):
    return path.read_text(encoding="utf-8")


def _browser_app_runtime_text():
    return _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/browser-app-runtime.js")


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
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
        ROOT / "src/embedagent/frontend/runtime/session_client_runtime.py",
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
        ROOT / "src/embedagent/frontend/runtime/session_client_runtime.py",
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
    text = "\n".join(_read(path) for path in sorted((ROOT / "src/embedagent/cli").glob("*.py")))
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
        / "docs/platform/frontend-protocol.md": (
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
        PROTOCOL_SOURCE / "__init__.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py",
        ROOT / "packages/embedagent-host/src/embedagent_host/hosted_interaction_service.py",
        ROOT / "src/embedagent/frontend/runtime/session_client_runtime.py",
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
    result = []
    for root in roots:
        candidates = [root] if root.is_file() else list(root.rglob("*.md"))
        for path in candidates:
            rel = _relative(path)
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


def test_active_docs_use_current_domain_paths_and_vocabulary():
    active_docs = {str(_relative(path)): _read(path) for path in _active_contract_doc_files()}
    joined = "\n".join(active_docs.values())
    forbidden = (
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

    docs_map = active_docs["docs/README.md"]
    architecture = active_docs["docs/overall-solution-architecture.md"]
    harness = active_docs["docs/applications/cpp-workflow.md"]
    frontend_protocol = active_docs["docs/platform/frontend-protocol.md"]
    component_path = "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/component.py"
    profile_path = "packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/profile.py"

    assert "docs/applications/cpp-workflow.md" in docs_map
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

    assert "createSessionListController" not in app_text
    assert "createSessionListController" in _browser_app_runtime_text()
    assert "sessionListController.loadSessions" in _browser_app_runtime_text()
    assert "async function loadSessions" not in app_text
    assert 'fetchJson("/api/sessions")' not in app_text
    assert 'type: "sessions_loaded"' not in app_text
    assert "export function createSessionListController" in controller_text
    assert "listSessions" in controller_text
    assert '"/api/"' not in controller_text
    assert 'type: "sessions_loaded"' in controller_text


def test_gui_session_activation_bootstrap_is_session_runtime_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    browser_text = _browser_app_runtime_text()
    runtime_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js"
    )
    python_runtime_text = _read(ROOT / "src/embedagent/frontend/runtime/session_client_runtime.py")
    session_controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-controller.js"
    )
    interaction_controller_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/app-runtime/interaction-response-controller.js"
    )

    assert "SessionClientRuntime" not in app_text
    assert "new SessionClientRuntime" in browser_text
    assert "sessionRuntime.activateSession" in browser_text
    assert "async function loadSession" not in app_text
    assert "deriveSessionActivation" not in app_text
    assert "deriveSessionActivation" in browser_text
    assert 'type: "session_activated"' in browser_text
    assert 'type: "terminal_summaries_loaded"' in browser_text
    assert "async activateSession" in runtime_text
    assert "async createSession" in runtime_text
    assert "async setSessionMode" in runtime_text
    assert "async cancelSession" in runtime_text
    assert "async respondToInteraction" in runtime_text
    assert "recoveryAttempted" in runtime_text
    assert "_sync_phase" in python_runtime_text
    assert "_event_queue" in python_runtime_text
    assert "_drain_event_queue" in python_runtime_text
    for retired_name in (
        "_activating",
        "_recovering",
        "_buffered_events",
        "_drain_buffered_events",
    ):
        assert retired_name not in python_runtime_text
    assert "syncPhase" in runtime_text
    assert "eventQueue" in runtime_text
    assert "#drainEventQueue" in runtime_text
    for retired_name in (
        "this.activating",
        "this.recovering",
        "activationBuffer",
        "#drainBufferedEvents",
    ):
        assert retired_name not in runtime_text
    assert (
        "for envelope in buffered:\n            self.on_session_event(envelope)"
        not in python_runtime_text
    )
    assert "for (const event of buffered) await this.acceptSessionEvent(event)" not in runtime_text
    assert "installSessionBootstrap" not in runtime_text
    assert "installSessionBootstrap" not in browser_text
    assert "installSessionBootstrap" not in session_controller_text
    assert "installSessionBootstrap" not in interaction_controller_text
    assert 'requireSessionRuntimeMethod(sessionRuntime, "createSession")' in (
        session_controller_text
    )
    assert "sessionRuntime.respondToInteraction" in interaction_controller_text
    assert not (
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-activation-controller.js"
    ).exists()


def test_gui_transports_and_protocol_are_composed_outside_app():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    main_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/main.jsx")
    http_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/client-runtime/http-transport.js"
    )
    socket_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/client-runtime/socket-transport.js"
    )
    protocol_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/client-runtime/protocol-adapter.js"
    )

    assert "function App({ protocol })" in app_text
    assert "fetch(" not in app_text
    assert "createHttpTransport" in main_text
    assert "createSocketTransport" in main_text
    assert "createAgentAppProtocolAdapter" in main_text
    assert "<App protocol={protocol} />" in main_text
    assert "return fetch(" in http_text
    assert "new WebSocketConstructor" in socket_text
    assert "fetchJson:" not in protocol_text
    assert "request," not in protocol_text


def test_gui_wire_effects_have_single_declared_owners():
    source_root = ROOT / "src/embedagent/frontend/gui/webapp/src"
    source_files = _source_files_under(
        "src/embedagent/frontend/gui/webapp/src",
        suffixes=(".js", ".jsx"),
    )

    def owners(pattern):
        return {
            path.relative_to(source_root).as_posix()
            for path in source_files
            if re.search(pattern, _read(path))
        }

    assert owners(r"/api/") == {"client-runtime/protocol-adapter.js"}
    assert owners(r"\bfetch\s*\(") == {"client-runtime/http-transport.js"}
    assert owners(r"\bWebSocket(?:Constructor)?\b") == {"client-runtime/socket-transport.js"}


def test_frontend_protocol_sources_do_not_keep_retired_wire_readers():
    frontend_files = _source_files_under(
        "src/embedagent/frontend/gui/backend",
        "src/embedagent/frontend/gui/webapp/src",
        "src/embedagent/frontend/tui",
    )
    frontend_source = "\n".join(_read(path) for path in frontend_files)
    for token in (
        "camelOrSnake",
        "fetchJson",
    ):
        assert token not in frontend_source

    python_source = "\n".join(
        _read(path)
        for path in _source_files_under(
            "packages",
            "src",
            suffixes=(".py",),
        )
    )
    assert "ThreadDetailSnapshot" not in python_source


def test_gui_initial_app_load_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/initial-app-load-controller.js"
    )

    assert "createInitialAppLoadController" not in app_text
    assert "createInitialAppLoadController" in _browser_app_runtime_text()
    assert "loadAppBootstrap();" not in app_text
    assert "loadSessionCommandCapabilities({ fetchJson, dispatch }).catch" not in app_text
    assert "createSessionCommandCapabilityLoader" not in app_text
    assert "createSessionCommandCapabilityLoader" in _browser_app_runtime_text()
    assert "loadSessionCommandCapabilities" in _browser_app_runtime_text()
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

    assert "createSocketMessageController" not in app_text
    assert "createSocketMessageController" in _browser_app_runtime_text()
    assert "createSocketEffectExecutor" not in app_text
    assert "const executeSocketEffects = createSocketEffectExecutor" not in app_text
    assert "function handleSocketMessage" not in app_text
    assert "deriveSocketMessageEffects" not in app_text
    assert "appendSessionTransportEvent" not in app_text
    assert "transportEvents.length" not in app_text
    assert 'nextTransport.reloadState === "reload_required"' not in app_text
    assert "for (const action of effects.actions" not in app_text
    assert "sessionRuntime.acceptSessionEvent" in _browser_app_runtime_text()
    assert "startTransition(() => socketMessageController.handleMessage" not in app_text
    assert "handleMessage: (message) =>" not in app_text
    assert "scheduleMessage: browserRuntime.scheduleMessage" in _browser_app_runtime_text()
    assert "socketMessageController?.handleAcceptedSessionEvent" in _browser_app_runtime_text()
    assert "export function createSocketMessageController" in controller_text
    assert "deriveSocketMessageEffects" in controller_text
    assert "createSocketEffectExecutor" in controller_text
    assert "scheduleMessage" in controller_text
    assert "function handleMessage" in controller_text
    assert "function handleAcceptedSessionEvent" in controller_text
    assert "export function createSocketEffectExecutor" in executor_text
    assert "applySessionTransportEvent" not in executor_text
    assert 'typeof loadSession === "function"' not in executor_text
    assert "transportEvents" not in executor_text
    assert "executeLoaderRequest" in executor_text


def test_gui_session_transport_projection_is_browser_runtime_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    browser_text = _browser_app_runtime_text()
    handle_path = (
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-handle.js"
    )

    assert "createSessionTransportHandle" not in app_text
    assert "createSessionTransportHandle" not in browser_text
    assert "sessionTransportRef" not in app_text
    assert "function replaceSessionTransport" not in app_text
    assert "function updateSessionTransport" not in app_text
    assert "function createRuntimeSessionTransport" not in app_text
    assert "function updateSessionTransport" in browser_text
    assert "projectSessionRuntime" in browser_text
    assert "createSessionTransportState" in browser_text
    assert not handle_path.exists()


def test_gui_session_transport_has_single_cursor_and_recovery_owner():
    adapter_text = _read(ROOT / "packages/embedagent-host/src/embedagent_host/inprocess_adapter.py")
    payload_text = _read(ROOT / "src/embedagent/frontend/gui/backend/protocol_payloads.py")
    runtime_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js"
    )
    transport_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-transport-controller.js"
    )
    executor_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/socket-effect-executor.js"
    )

    assert "self._event_emitter.capture(" in adapter_text
    assert "event_cursor=event_cursor" in payload_text
    assert "this.cursor" in runtime_text
    assert "this.generation" in runtime_text
    assert "this.recoveryAttempted" in runtime_text
    assert "lastAppliedSeq: Number(state?.lastAppliedSeq" not in transport_text
    assert "clearTimeout" in transport_text
    assert "token += 1" in transport_text
    assert "applyEvent" not in transport_text
    assert "function recover" not in transport_text
    assert 'typeof loadSession === "function"' not in executor_text
    assert "transportEvents" not in executor_text


def test_gui_responding_request_ids_bridge_is_handle_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    handle_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/responding-request-ids-handle.js"
    )

    assert "createRespondingRequestIdsHandle" not in app_text
    assert "createRespondingRequestIdsHandle" in _browser_app_runtime_text()
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
    assert "base_agent_application_registry" not in adapter_text
    assert "ApplicationConfigurationError" in adapter_text
    assert "product_agent_application_registry" in product_hosted_text
    assert "agentApplication" in adapter_text
    assert "agentApplications" in adapter_text
    assert "AgentApplicationRecord" in application_registry_text
    assert "AgentApplicationRegistry" in application_registry_text
    assert "BUILTIN_AGENT_APPLICATION_RECORDS" in application_registry_text
    assert "embedagent_workflow_cpp" not in application_registry_text
    assert "default_c_cpp_application_record" not in application_registry_text
    assert "default_c_cpp_application_record" not in product_registry_text
    assert "DEFAULT_C_CPP_AGENT_APPLICATION_ID" not in product_registry_text
    assert "selected_application_registry" in product_hosted_text
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

    assert 'DEFAULT_MODE = "explore"' not in store_text
    assert 'defaultMode = "explore"' not in state_helpers_text
    assert 'options.defaultMode || "explore"' not in session_loaders_text
    assert 'defaultMode = "explore"' not in activity_state_text
    assert 'session.current_mode || session.mode || "explore"' not in command_palette_text
    assert "DEFAULT_MODE" not in gui_routes_text
    assert "DEFAULT_MODE" not in gui_protocol_text


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


def test_frontend_protocol_has_no_split_task_or_recipe_facade():
    protocol_text = _read(PROTOCOL_SOURCE / "__init__.py")

    for token in (
        "def list_workspace_recipes",
        "def list_tasks",
    ):
        assert token not in protocol_text


def test_gui_has_no_split_tool_catalog_facade():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    app_workspaces_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/app-workspaces.js")
    routes_text = _read(ROOT / "src/embedagent/frontend/gui/backend/routes_sessions.py")
    protocol_text = _read(PROTOCOL_SOURCE / "__init__.py")

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


def test_gui_visual_debug_installation_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    controller_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-controller.js"
    )
    fixtures_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/visual-debug-fixtures.js"
    )

    assert "createVisualDebugController" not in app_text
    assert "createVisualDebugController" in _browser_app_runtime_text()
    assert "installVisualDebugFixtures" not in app_text
    assert "__EMBEDAGENT_VISUAL_DEBUG__" not in app_text
    assert "window.location.search" not in app_text
    assert "export function createVisualDebugController" in controller_text
    assert "installVisualDebugFixtures" in controller_text
    assert "getLocationSearch" in controller_text
    assert "getCurrentMode" in controller_text
    assert "export function installVisualDebugFixtures" in fixtures_text


def test_gui_has_no_retired_inspector_sidecar_state():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    store_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/store.js")
    inspector_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )
    loaders_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/session-loaders.js"
    )
    session_runtime_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js"
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
        assert token not in session_runtime_text
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
        assert token not in gui_server_text
        assert token not in gui_routes_text


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

    tool_contracts_text = _read(ROOT / "docs/platform/tool-contracts.md")
    for token in (
        "`workspace_files`, `tasks`, or `artifacts`",
        "file/task/artifact refresh",
    ):
        assert token not in tool_contracts_text


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
        "src/embedagent/frontend/gui/webapp/src/app-runtime/browser-app-runtime.js": (
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


def test_gui_active_workspace_data_loading_is_controller_owned():
    app_text = _read(ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx")
    loader_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/app-runtime/active-workspace-data-loader.js"
    )

    assert "createActiveWorkspaceDataLoader" not in app_text
    assert "createActiveWorkspaceDataLoader" in _browser_app_runtime_text()
    assert (
        "loadWorkspaceData: activeWorkspaceDataLoader.loadActiveWorkspaceData"
        in _browser_app_runtime_text()
    )
    assert "Promise.all([" not in app_text
    assert 'loadFileChildren(".", { appCapabilities' not in app_text
    assert "sourceControlController.loadStatus(false, assumeWorkspace" not in app_text
    assert "loadStatus: sourceControlController.loadStatus" in _browser_app_runtime_text()
    assert "loadStatus: (refresh, assumeWorkspace, appCapabilities)" not in app_text
    assert (
        "sourceControlController.loadStatus(refresh, assumeWorkspace, appCapabilities)"
        not in app_text
    )
    assert "export function createActiveWorkspaceDataLoader" in loader_text
    assert "Promise.all([" in loader_text
    assert 'invoke(loadFileChildren, ".",' in loader_text
    assert "invoke(loadStatus, false," in loader_text


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


def test_frontend_root_is_a_minimal_agent_shell_composition():
    app_path = ROOT / "src/embedagent/frontend/gui/webapp/src/App.jsx"
    app_text = _read(app_path)
    assert len(app_text.splitlines()) <= 12
    assert 'from "./client-runtime/use-agent-shell-runtime.js"' in app_text
    assert 'from "./components/shell/AgentShell.jsx"' in app_text
    assert "<AgentShell" in app_text
    for forbidden in (
        "TerminalShell",
        "SourceControlPanel",
        "PreviewSurface",
        "SurfacePanel",
        "fetch(",
        "WebSocket",
    ):
        assert forbidden not in app_text


def test_frontend_optional_features_enter_only_through_contribution_registry():
    shell_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/shell/AgentShell.jsx"
    )
    registry_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/contributions/renderer-registry.js"
    )
    surface_text = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/components/SurfacePanel.jsx"
    )
    outlet_text = _read(
        ROOT
        / "src/embedagent/frontend/gui/webapp/src/components/contributions/ContributionOutlet.jsx"
    )
    assert "<ContributionOutlet" in shell_text
    for optional_component in (
        "TerminalShell",
        "PreviewSurface",
        "FilePreviewSurface",
    ):
        assert optional_component not in shell_text
        assert optional_component in registry_text
    assert "SourceControlPanel" not in shell_text
    assert "SurfacePanel" in registry_text
    assert "SourceControlPanel" in surface_text
    assert "contributionRenderer" in outlet_text
    assert "switch (" not in outlet_text


def test_product_compiles_one_shell_descriptor_for_gui_and_tui():
    compiler_text = _read(ROOT / "src/embedagent/frontend/shell/compiler.py")
    gui_launcher_text = _read(ROOT / "src/embedagent/frontend/gui/launcher.py")
    tui_launcher_text = _read(ROOT / "src/embedagent/frontend/tui/launcher.py")
    app_shell_text = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell.py")
    assert "def compile_shell_descriptor" in compiler_text
    assert "ShellDescriptor(" in compiler_text
    assert "compile_generic_shell_descriptor" in gui_launcher_text
    assert "compile_generic_shell_descriptor" in tui_launcher_text
    assert "self._shell_compiler" in app_shell_text
    assert not (ROOT / "src/embedagent/frontend/gui/backend/app_shell_spec.py").exists()


def test_tui_core_has_four_regions_and_no_auxiliary_panel_state():
    layout_text = _read(ROOT / "src/embedagent/frontend/tui/layout.py")
    state_text = _read(ROOT / "src/embedagent/frontend/tui/state.py")
    shell_state_text = _read(ROOT / "src/embedagent/frontend/tui/shell_state.py")
    assert 'core_region_ids = ("header", "timeline", "composer", "status")' in layout_text
    assert "state.contributions" in layout_text
    assert "ShellState" in state_text
    assert "contributions:" in state_text
    for forbidden in (
        "right_panel",
        "bottom_drawer",
        "WorkbenchState",
        "active_surface",
        "active_drawer",
    ):
        assert forbidden not in state_text
        assert forbidden not in shell_state_text


def test_generic_frontend_layers_do_not_expand_cpp_workflow_semantics():
    roots = (
        ROOT / "packages/embedagent-protocol/src",
        ROOT / "packages/embedagent-host/src",
        ROOT / "src/embedagent/frontend",
    )
    forbidden = (
        "current_phase",
        "discipline_profile",
        "current_activity",
        "task_summary",
        "task_items",
    )
    offenders = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            text = _read(path)
            for token in forbidden:
                if token in text:
                    offenders.append("%s contains %s" % (_relative(path), token))
    assert offenders == []


def test_retired_frontend_facades_and_callback_injection_are_absent():
    source_files = _source_files_under(
        "packages/embedagent-protocol/src",
        "packages/embedagent-host/src",
        "src/embedagent",
        suffixes=(".py",),
    )
    forbidden_tokens = (
        "CoreInterface",
        "FrontendCallbacks",
        "AgentCoreAdapter",
        "HostedSessionHost",
        "session_host.adapter",
        "permission_resolver",
        "user_input_resolver",
    )
    forbidden_patterns = (
        re.compile(r"\bevent_handler\s*="),
        re.compile(
            r"def\s+on_event\s*\(\s*(?:self\s*,\s*)?event_name\s*,\s*session_id\s*,\s*payload"
        ),
    )
    offenders = []
    for path in source_files:
        source = _read(path)
        relative = _relative(path)
        for token in forbidden_tokens:
            if token in source:
                offenders.append("%s contains %s" % (relative, token))
        for pattern in forbidden_patterns:
            if pattern.search(source):
                offenders.append("%s matches %s" % (relative, pattern.pattern))
    assert offenders == []


def test_shared_client_runtimes_do_not_branch_on_product_semantics():
    files = _source_files_under(
        "src/embedagent/frontend/runtime",
        "src/embedagent/frontend/gui/webapp/src/client-runtime",
        "src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js",
        suffixes=(".py", ".js", ".jsx"),
    )
    semantic_names = (
        "agent_application_id",
        "applicationId",
        "workflow_type",
        "workflowType",
        "read_file",
        "list_dir",
        "glob_files",
        "grep_text",
        "write_file",
        "edit_file",
        "author_local_capability",
        "bash",
        "ask_user",
        "list_recipes",
        "run_recipe",
        "report_quality_v2",
        "record_failing_evidence",
        "task_status",
    )
    comparison = re.compile(
        r"(?:==|===|!=|!==)\s*[\"'](%s)[\"']|[\"'](%s)[\"']\s*(?:==|===|!=|!==)"
        % ("|".join(semantic_names), "|".join(semantic_names))
    )
    offenders = []
    for path in files:
        source = _read(path)
        if comparison.search(source):
            offenders.append(_relative(path))
    assert offenders == []


def test_frontend_transport_primitives_have_focused_owners():
    gui_root = ROOT / "src/embedagent/frontend/gui/webapp/src"
    allowed = {
        "client-runtime/http-transport.js",
        "client-runtime/socket-transport.js",
    }
    offenders = []
    for path in gui_root.rglob("*"):
        if not path.is_file() or path.suffix not in (".js", ".jsx"):
            continue
        text = _read(path)
        if re.search(r"\b(fetch|WebSocket|XMLHttpRequest)\b", text):
            relative = path.relative_to(gui_root).as_posix()
            if relative not in allowed:
                offenders.append(relative)
    assert offenders == []


def test_frontend_migration_names_and_retired_paths_do_not_return():
    gui_root = ROOT / "src/embedagent/frontend/gui/webapp"
    offenders = []
    for directory in (gui_root / "src", gui_root / "test"):
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix not in (".js", ".jsx", ".css", ".mjs"):
                continue
            if re.search(r"t3[-_]|parity", path.name, re.IGNORECASE):
                offenders.append(_relative(path))
            if re.search(r"t3[-_]|parity", _read(path), re.IGNORECASE):
                offenders.append(_relative(path))
    retired = (
        "src/embedagent/frontend/gui/backend/app_shell_spec.py",
        "src/embedagent/frontend/gui/webapp/src/session-runtime/t3-timeline.js",
        "src/embedagent/frontend/gui/webapp/src/workbench/workbench-parity-model.js",
        "src/embedagent/frontend/gui/webapp/src/workbench/surfaces.js",
        "src/embedagent/frontend/gui/webapp/src/workbench/ui-state.js",
        "src/embedagent/frontend/gui/webapp/src/app-runtime/right-panel-controller.js",
        "src/embedagent/frontend/gui/webapp/src/app-runtime/panel-resize-controller.js",
        "src/embedagent/frontend/gui/webapp/src/components/workbench/RightPanelTabs.jsx",
        "src/embedagent/frontend/gui/webapp/src/components/workbench/BottomDrawer.jsx",
        "src/embedagent/frontend/tui/workbench.py",
        "src/embedagent/frontend/tui/views/explorer.py",
        "src/embedagent/frontend/tui/views/editor.py",
        "src/embedagent/frontend/tui/views/inspector.py",
    )
    assert offenders == []
    assert [path for path in retired if (ROOT / path).exists()] == []


def test_frontend_source_owners_stay_focused():
    source_root = ROOT / "src/embedagent/frontend/gui/webapp/src"
    oversized = []
    for path in source_root.rglob("*"):
        if not path.is_file() or path.suffix not in (".js", ".jsx", ".css"):
            continue
        limit = 800 if path.suffix == ".css" else 1000
        lines = len(_read(path).splitlines())
        if lines > limit:
            oversized.append("%s has %s lines" % (_relative(path), lines))
    assert oversized == []
    assert _read(source_root / "styles.css").splitlines() == [
        '@import "./styles/tokens.css";',
        '@import "./styles/base.css";',
        '@import "./styles/shell.css";',
        '@import "./styles/timeline.css";',
        '@import "./styles/composer.css";',
        '@import "./styles/overlays.css";',
        '@import "./styles/contributions.css";',
    ]


def test_frontend_v2_failure_and_workspace_contracts_stay_canonical():
    protocol = _read(ROOT / "packages/embedagent-protocol/src/embedagent_protocol/app_protocol.py")
    app_shell = _read(ROOT / "src/embedagent/frontend/gui/backend/app_shell.py")
    normalizer = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/protocol-normalizer.js"
    )
    assert "last_failure" in protocol
    assert "last_error" not in app_shell
    assert '"last_failure"' in normalizer
    assert '"last_error"' not in normalizer


def test_generic_host_runtime_has_no_concrete_provider_construction():
    source = _read(ROOT / "packages/embedagent-host/src/embedagent_host/hosted/runtime.py")
    for forbidden in (
        "OpenAICompatibleClient(",
        "ToolRuntime(",
        "ContextManager(",
        "PermissionPolicy(",
        "ProjectMemoryStore(",
        "SessionSummaryStore(",
    ):
        assert forbidden not in source
    assert "model_client=None" in source
    assert "tool_runtime=None" in source
    assert "ApplicationConfigurationError" in source


def test_gui_session_event_acceptance_uses_strict_normalizer():
    runtime = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/session-client-runtime.js"
    )
    transport = _read(
        ROOT / "src/embedagent/frontend/gui/webapp/src/session-runtime/session-transport-state.js"
    )
    assert "normalizeSessionEventEnvelope" in runtime
    assert "normalizeSessionEventEnvelope" in transport


def test_cli_sessions_and_tui_use_runtime_failure_projection():
    sessions = _read(ROOT / "src/embedagent/cli/sessions.py")
    tui_files = "\n".join(
        _read(path) for path in (ROOT / "src/embedagent/frontend/tui").rglob("*.py")
    )
    assert "context.session_port" not in sessions
    assert "last_error" not in tui_files
    assert "set_last_failure" in tui_files
