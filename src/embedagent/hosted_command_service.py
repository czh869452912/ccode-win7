from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from embedagent.modes import require_mode
from embedagent.permissions import PermissionRequest
from embedagent.prompts import expand_prompt_invocation
from embedagent.protocol import CommandResult, PlanSnapshot
from embedagent.review_command import ReviewCommandService
from embedagent.session import Action, AssistantReply, Observation
from embedagent.session_runtime import ManagedSession
from embedagent.skills import expand_skill_invocation
from embedagent.slash_command_service import SlashCommandService
from embedagent.slash_commands import (
    ParsedSlashCommand,
    SlashCommandRegistry,
    parse_slash_command,
    resource_command_specs,
)

EventHandler = Callable[[str, str, Dict[str, Any]], None]
PermissionResolver = Callable[[Dict[str, Any]], bool]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class HostedCommandService(object):
    """Hosted slash-command shell around session/runtime services."""

    def __init__(
        self,
        tools: Any,
        command_registry: SlashCommandRegistry,
        plan_store: Any,
        max_turns: Optional[int],
        require_session: Callable[[str], ManagedSession],
        set_session_mode: Callable[[str, str], Dict[str, Any]],
        resume_session: Callable[..., Dict[str, Any]],
        list_sessions: Callable[..., List[Dict[str, Any]]],
        get_workspace_snapshot: Callable[[], Dict[str, Any]],
        list_workspace_recipes: Callable[[], Dict[str, Any]],
        reload_resources: Callable[..., Dict[str, Any]],
        list_tasks: Callable[..., Dict[str, Any]],
        list_artifacts: Callable[..., List[Dict[str, Any]]],
        get_permission_context: Callable[[str], Any],
        emit: Callable[[Optional[EventHandler], str, str, Dict[str, Any]], None],
        emit_with_snapshot: Callable[
            [Optional[EventHandler], str, ManagedSession, Dict[str, Any]], None
        ],
        notify_status: Callable[[Optional[EventHandler], ManagedSession], None],
        persist_state: Callable[[ManagedSession], None],
        refresh_harness_state: Callable[[ManagedSession], None],
        tool_event_metadata: Callable[[str], Dict[str, Any]],
        create_permission_ticket: Callable[..., Any],
        clear_pending_permission: Callable[[ManagedSession], None],
    ) -> None:
        self.tools = tools
        self.command_registry = command_registry
        self.plan_store = plan_store
        self.review_command = ReviewCommandService(tools)
        self.max_turns = max_turns
        self._require_session = require_session
        self._set_session_mode = set_session_mode
        self._resume_session = resume_session
        self._list_sessions = list_sessions
        self._get_workspace_snapshot = get_workspace_snapshot
        self._list_workspace_recipes = list_workspace_recipes
        self._reload_resources = reload_resources
        self._list_tasks = list_tasks
        self._list_artifacts = list_artifacts
        self._get_permission_context = get_permission_context
        self._emit = emit
        self._emit_with_snapshot = emit_with_snapshot
        self._notify_status = notify_status
        self._persist_state = persist_state
        self._refresh_harness_state = refresh_harness_state
        self._tool_event_metadata = tool_event_metadata
        self._create_permission_ticket = create_permission_ticket
        self._clear_pending_permission = clear_pending_permission
        self._slash_commands = SlashCommandService(
            {
                "help": self._handle_command_help,
                "mode": self._handle_command_mode,
                "sessions": self._handle_command_sessions,
                "resume": self._handle_command_resume,
                "workspace": self._handle_command_workspace,
                "recipes": self._handle_command_recipes,
                "resources": self._handle_command_resources,
                "run": self._handle_command_run,
                "clear": self._handle_command_clear,
                "tasks": self._handle_command_tasks,
                "artifacts": self._handle_command_artifacts,
                "diff": self._handle_command_diff,
                "permissions": self._handle_command_permissions,
                "plan": self._handle_command_plan,
                "review": self._handle_command_review,
            }
        )

    def dispatch(
        self,
        state: ManagedSession,
        text: str,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        parsed = parse_slash_command(text)
        if parsed is None:
            return {"handled": False, "continue_with_text": text}
        if parsed.name.startswith("skill:"):
            return self._dispatch_skill_command(state, parsed, event_handler)
        if parsed.name.startswith("prompt:"):
            return self._dispatch_prompt_command(state, parsed, event_handler)
        spec = self.command_registry.get(parsed.name)
        if spec is None:
            self.emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name=parsed.name,
                    success=False,
                    message="未知命令：/%s" % parsed.name,
                    data={"raw_args": parsed.raw_args},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        with state.lock:
            state.current_command_context = parsed.name
            if parsed.name in ("plan", "review"):
                state.workflow_state = parsed.name
            else:
                state.workflow_state = "command"
            state.updated_at = _utc_now()
        handler = self._slash_commands.handler_for(parsed.name)
        if not callable(handler):
            self.emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name=parsed.name,
                    success=False,
                    message="命令尚未实现：/%s" % parsed.name,
                    data={"raw_args": parsed.raw_args},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        return handler(state, parsed, event_handler, permission_resolver)

    def emit_command_result(
        self,
        event_handler: Optional[EventHandler],
        state: ManagedSession,
        result: CommandResult,
    ) -> None:
        state.engine.record_command_result(
            state.session,
            user_text=state.current_command_text,
            command_name=result.command_name,
            success=result.success,
            message=result.message,
            data=result.data if isinstance(result.data, dict) else {},
            turn_id=result.turn_id or state.current_command_turn_id,
            step_id=result.step_id or state.current_command_step_id,
            step_index=result.step_index or state.current_command_step_index,
        )
        payload = {
            "command_name": result.command_name,
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "turn_id": result.turn_id or state.current_command_turn_id,
            "step_id": result.step_id or state.current_command_step_id,
            "step_index": result.step_index or state.current_command_step_index,
        }
        self._emit_with_snapshot(event_handler, "command_result", state, payload)

    def _dispatch_skill_command(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
    ) -> Dict[str, Any]:
        resources = self.tools.local_resources()
        expanded_text, error = expand_skill_invocation(
            "/%s %s" % (parsed.name, parsed.raw_args), resources, self.tools.workspace
        )
        if error:
            self.emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name=parsed.name,
                    success=False,
                    message=error,
                    data={"raw_args": parsed.raw_args},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        return {"handled": True, "continue_with_text": expanded_text}

    def _dispatch_prompt_command(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
    ) -> Dict[str, Any]:
        resources = self.tools.local_resources()
        expanded_text, error = expand_prompt_invocation(
            "/%s %s" % (parsed.name, parsed.raw_args), resources, self.tools.workspace
        )
        if error:
            self.emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name=parsed.name,
                    success=False,
                    message=error,
                    data={"raw_args": parsed.raw_args},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        return {"handled": True, "continue_with_text": expanded_text}

    def _handle_command_help(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        resources = self.tools.local_resources()
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="help",
                success=True,
                message=self.command_registry.help_markdown(
                    extra_specs=resource_command_specs(resources)
                ),
                data={
                    "commands": [
                        item.name
                        for item in self.command_registry.specs(
                            extra_specs=resource_command_specs(resources)
                        )
                    ]
                },
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_mode(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        if not parsed.args:
            self.emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name="mode",
                    success=True,
                    message="当前模式：`%s`" % state.current_mode,
                    data={"current_mode": state.current_mode},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        target_mode = require_mode(parsed.args[0])["slug"]
        remainder = ""
        if parsed.raw_args:
            parts = parsed.raw_args.split(None, 1)
            remainder = str(parts[1] or "").strip() if len(parts) > 1 else ""
        snapshot = self._set_session_mode(state.session.session_id, target_mode)
        message = "已切换到 `%s` 模式。" % target_mode
        if remainder:
            message += " 继续处理后续消息。"
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="mode",
                success=True,
                message=message,
                data={"current_mode": target_mode, "session_snapshot": snapshot},
            ),
        )
        return {"handled": True, "continue_with_text": remainder}

    def _handle_command_sessions(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        sessions = self._list_sessions(limit=10)
        lines = ["## Recent Sessions", ""]
        if not sessions:
            lines.append("当前没有可恢复会话。")
        else:
            for item in sessions:
                label = str(
                    item.get("user_goal")
                    or item.get("summary_text")
                    or item.get("session_id")
                    or ""
                )
                lines.append(
                    "- `%s` [%s] %s"
                    % (
                        str(item.get("session_id") or "")[:12],
                        str(item.get("current_mode") or "-"),
                        label[:96],
                    )
                )
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="sessions",
                success=True,
                message="\n".join(lines),
                data={"sessions": sessions},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_resume(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        reference = parsed.args[0] if parsed.args else "latest"
        mode = parsed.args[1] if len(parsed.args) > 1 else state.current_mode
        snapshot = self._resume_session(reference, mode, event_handler=event_handler)
        self.emit_command_result(
            event_handler,
            self._require_session(str(snapshot.get("session_id") or "")),
            CommandResult(
                command_name="resume",
                success=True,
                message="已恢复会话 `%s`。" % str(snapshot.get("session_id") or ""),
                data={
                    "session_snapshot": snapshot,
                    "switch_session_id": str(snapshot.get("session_id") or ""),
                },
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_workspace(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        payload = self._get_workspace_snapshot()
        git_payload = payload.get("git") if isinstance(payload.get("git"), dict) else {}
        tree_payload = payload.get("tree") if isinstance(payload.get("tree"), dict) else {}
        recipe_payload = payload.get("recipes") if isinstance(payload.get("recipes"), dict) else {}
        lines = [
            "## Workspace",
            "",
            "- path: `%s`" % payload.get("workspace", ""),
            "- branch: `%s`" % git_payload.get("branch", ""),
            "- dirty files: %s" % git_payload.get("dirty_count", 0),
            "- files: %s" % tree_payload.get("file_count", 0),
            "- dirs: %s" % tree_payload.get("dir_count", 0),
            "- recipes: %s" % int(recipe_payload.get("count") or 0),
        ]
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="workspace",
                success=True,
                message="\n".join(lines),
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_recipes(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        payload = self._list_workspace_recipes()
        items = payload.get("items") or []
        lines = ["## Workspace Recipes", ""]
        if not items:
            lines.append("当前工作区没有可用 recipe。")
        else:
            for item in items:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "- `%s` [%s] %s"
                    % (
                        str(item.get("id") or ""),
                        str(item.get("tool_name") or ""),
                        str(item.get("label") or item.get("command") or ""),
                    )
                )
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="recipes",
                success=True,
                message="\n".join(lines),
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_resources(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        action = parsed.args[0] if parsed.args else "list"
        if str(action or "").strip().lower() == "reload":
            payload = self._reload_resources(
                session_id=state.session.session_id,
                reason="command",
            )
        else:
            lookup = getattr(self.tools, "local_resources", None)
            payload = (
                lookup()
                if callable(lookup)
                else self._reload_resources(session_id=state.session.session_id, reason="command")
            )
        counts = dict(payload.get("counts") or {})
        lines = [
            "## Local Resources",
            "",
            "- skills: %s" % int(counts.get("skills") or 0),
            "- prompts: %s" % int(counts.get("prompts") or 0),
            "- recipes: %s" % int(counts.get("recipes") or 0),
            "- diagnostics: %s" % int(counts.get("diagnostics") or 0),
        ]
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="resources",
                success=True,
                message="\n".join(lines),
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_run(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        if not parsed.args:
            self.emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name="run",
                    success=False,
                    message="用法：`/run <recipe_id>`",
                    data={},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        recipe_id = str(parsed.args[0] or "").strip()
        target = str(parsed.args[1] or "").strip() if len(parsed.args) > 1 else ""
        profile = str(parsed.args[2] or "").strip() if len(parsed.args) > 2 else ""
        recipes_payload = self._list_workspace_recipes()
        recipe_items = recipes_payload.get("items") or []
        matched = None
        for item in recipe_items:
            if isinstance(item, dict) and str(item.get("id") or "") == recipe_id:
                matched = item
                break
        if matched is None:
            self.emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name="run",
                    success=False,
                    message="未找到 recipe：`%s`" % recipe_id,
                    data={"recipe_id": recipe_id},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        observation = self._execute_tool_from_command(
            state=state,
            command_text="/run %s" % parsed.raw_args,
            tool_name=str(matched.get("tool_name") or ""),
            arguments={"recipe_id": recipe_id, "target": target, "profile": profile},
            permission_resolver=permission_resolver,
            event_handler=event_handler,
        )
        success = bool(observation.success)
        message = (
            "已执行 recipe `%s`。" % recipe_id
            if success
            else "recipe `%s` 执行失败：%s" % (recipe_id, observation.error or "未知错误")
        )
        payload = dict(observation.data) if isinstance(observation.data, dict) else {}
        payload["recipe_id"] = recipe_id
        payload["tool_name"] = str(matched.get("tool_name") or "")
        payload["target"] = target
        payload["profile"] = profile
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="run",
                success=success,
                message=message,
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_clear(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="clear",
                success=True,
                message="已请求前端清空当前时间线视图。",
                data={"clear_session_view": True},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_tasks(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        payload = self._list_tasks(session_id=state.session.session_id)
        lines = ["## Session Tasks", ""]
        tasks = payload.get("tasks") or []
        if not tasks:
            lines.append("当前会话暂无任务。")
        else:
            for item in tasks:
                if not isinstance(item, dict):
                    continue
                prefix = "[x]" if item.get("done") else "[ ]"
                lines.append("- %s %s" % (prefix, str(item.get("content") or "")))
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="tasks",
                success=True,
                message="\n".join(lines),
                data=payload,
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_artifacts(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        items = self._list_artifacts(limit=20)
        lines = ["## Recent Artifacts", ""]
        if not items:
            lines.append("暂无工件。")
        else:
            for item in items:
                lines.append(
                    "- `%s` (%s)"
                    % (
                        str(item.get("path") or ""),
                        str(item.get("tool_name") or item.get("kind") or ""),
                    )
                )
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="artifacts",
                success=True,
                message="\n".join(lines),
                data={"items": items},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_diff(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        observation = self.tools.execute("git_diff", {"path": ".", "scope": "working"})
        diff_text = ""
        file_count = 0
        if observation.success and isinstance(observation.data, dict):
            diff_text = str(observation.data.get("diff") or "")
            file_count = int(observation.data.get("file_count") or 0)
        if not observation.success:
            message = "无法读取 Git diff：%s" % (observation.error or "未知错误")
        elif not diff_text:
            message = "当前工作区没有未提交 diff。"
        else:
            message = "## Git Diff\n\n- changed files: %s" % file_count
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="diff",
                success=observation.success,
                message=message,
                data=observation.data if isinstance(observation.data, dict) else {},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_permissions(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        context = self._get_permission_context(state.session.session_id)
        lines = [
            "## Permission Context",
            "",
            "- rules path: `%s`" % context.rules_path,
            "- remembered categories: %s" % (", ".join(context.remembered_categories) or "(none)"),
            "- rule count: %s" % len(context.rules),
        ]
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="permissions",
                success=True,
                message="\n".join(lines),
                data={
                    "session_id": context.session_id,
                    "rules_path": context.rules_path,
                    "categories": context.categories,
                    "rules": context.rules,
                    "remembered_categories": context.remembered_categories,
                    "auto_approve_all": context.auto_approve_all,
                    "auto_approve_writes": context.auto_approve_writes,
                    "auto_approve_commands": context.auto_approve_commands,
                },
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_plan(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        current = self.plan_store.load(state.session.session_id)
        if parsed.raw_args:
            summary = parsed.raw_args.splitlines()[0][:120]
            current = self.plan_store.save(
                state.session.session_id,
                title="Current Plan",
                content=parsed.raw_args,
                workflow_state="plan",
                summary=summary,
            )
            with state.lock:
                state.workflow_state = "plan"
                state.active_plan_ref = current.path
                state.updated_at = _utc_now()
            self._emit_plan_updated(event_handler, state, current)
            self.emit_command_result(
                event_handler,
                state,
                CommandResult(
                    command_name="plan",
                    success=True,
                    message="已更新当前计划。",
                    data={"plan": self._plan_to_dict(current)},
                ),
            )
            return {"handled": True, "continue_with_text": ""}
        if current is None:
            current = self.plan_store.save(
                state.session.session_id,
                title="Current Plan",
                content="## Summary\n\n- \n\n## Steps\n\n1. \n\n## Tests\n\n- \n\n## Assumptions\n\n- ",
                workflow_state="plan",
                summary="Current Plan",
            )
            with state.lock:
                state.workflow_state = "plan"
                state.active_plan_ref = current.path
        self._emit_plan_updated(event_handler, state, current)
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="plan",
                success=True,
                message=current.content,
                data={"plan": self._plan_to_dict(current)},
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _handle_command_review(
        self,
        state: ManagedSession,
        parsed: ParsedSlashCommand,
        event_handler: Optional[EventHandler],
        permission_resolver: Optional[PermissionResolver],
    ) -> Dict[str, Any]:
        review = self.review_command.build_payload_from_session(state.session, limit=400)
        lines = self.review_command.markdown_lines(review)
        self.emit_command_result(
            event_handler,
            state,
            CommandResult(
                command_name="review",
                success=True,
                message="\n".join(lines),
                data={
                    "review": review,
                },
            ),
        )
        return {"handled": True, "continue_with_text": ""}

    def _execute_tool_from_command(
        self,
        state: ManagedSession,
        command_text: str,
        tool_name: str,
        arguments: Dict[str, Any],
        permission_resolver: Optional[PermissionResolver],
        event_handler: Optional[EventHandler],
    ) -> Observation:
        action = Action(
            name=tool_name,
            arguments=dict(arguments),
            call_id="cmd-%s" % uuid.uuid4().hex[:10],
        )
        turn_id = state.current_command_turn_id
        with state.lock:
            state.status = "running"
            state.updated_at = _utc_now()
        self._notify_status(event_handler, state)
        current_step = {"step_id": "", "step_index": 0}

        def on_step_start(step_id: str, step_index: int) -> None:
            current_step["step_id"] = step_id
            current_step["step_index"] = step_index
            with state.lock:
                state.current_command_step_id = step_id
                state.current_command_step_index = step_index
            self._emit(
                event_handler,
                "step_start",
                state.session.session_id,
                {"turn_id": turn_id, "step_id": step_id, "step_index": step_index},
            )

        def on_step_finish(step_index: int, reply: AssistantReply, status: str) -> None:
            self._emit(
                event_handler,
                "step_end",
                state.session.session_id,
                {
                    "turn_id": turn_id,
                    "step_id": current_step["step_id"],
                    "step_index": step_index,
                    "assistant_text": reply.content or "",
                    "finish_reason": reply.finish_reason or "",
                    "status": status,
                },
            )

        def on_tool_start(start_action: Action) -> None:
            payload = {
                "tool_name": start_action.name,
                "arguments": start_action.arguments,
                "call_id": start_action.call_id,
                "turn_id": turn_id,
                "step_id": current_step["step_id"],
                "step_index": current_step["step_index"],
            }
            payload.update(self._tool_event_metadata(start_action.name))
            self._emit(event_handler, "tool_started", state.session.session_id, payload)

        def on_tool_finish(finished_action: Action, observation: Observation) -> None:
            payload = {
                "tool_name": finished_action.name,
                "success": observation.success,
                "error": observation.error,
                "data": observation.data,
                "call_id": finished_action.call_id,
                "turn_id": turn_id,
                "step_id": current_step["step_id"],
                "step_index": current_step["step_index"],
            }
            payload.update(self._tool_event_metadata(finished_action.name))
            self._emit_with_snapshot(event_handler, "tool_finished", state, payload)

        def permission_handler(request: PermissionRequest) -> Optional[bool]:
            ticket = self._create_permission_ticket(
                state,
                request,
                turn_id=turn_id,
                step_id=current_step["step_id"],
                step_index=current_step["step_index"],
            )
            self._emit_with_snapshot(
                event_handler,
                "permission_required",
                state,
                {
                    "permission": ticket.to_dict(),
                    "turn_id": ticket.turn_id,
                    "step_id": ticket.step_id,
                    "step_index": ticket.step_index,
                },
            )
            self._notify_status(event_handler, state)
            if permission_resolver is not None:
                approved = bool(permission_resolver(ticket.to_dict()))
                self._clear_pending_permission(state)
                return approved
            with state.lock:
                state.status = "waiting_permission"
                state.pending_event = threading.Event()
            return None

        result, observation = state.engine.submit_command_turn(
            user_text=command_text,
            action=action,
            initial_mode=state.current_mode,
            workflow_state=state.workflow_state,
            session=state.session,
            turn_id=turn_id,
            stop_event=state.stop_event,
            on_tool_start=on_tool_start,
            on_tool_finish=on_tool_finish,
            on_step_start=on_step_start,
            on_step_finish=on_step_finish,
            permission_handler=permission_handler,
            user_input_handler=None,
        )
        state.session = result.session
        if (
            result.transition.reason in ("permission_wait", "user_input_wait")
            and permission_resolver is None
        ):
            with state.lock:
                event = state.pending_event
            if event is not None:
                event.wait()
            approved = False
            with state.lock:
                approved = bool(state.pending_result)
                state.pending_event = None
                state.pending_result = None
                state.status = "running"
            resumed = state.engine.resume_interaction(
                session=state.session,
                initial_mode=state.current_mode,
                interaction_resolution={"approved": approved},
                workflow_state=state.workflow_state,
                stream=False,
                stop_event=state.stop_event,
                on_tool_start=on_tool_start,
                on_tool_finish=on_tool_finish,
                on_step_start=on_step_start,
                on_step_finish=on_step_finish,
                permission_handler=permission_handler,
                user_input_handler=None,
            )
            state.session = resumed.session
            result = resumed
            self._clear_pending_permission(state)
            if state.session.turns and state.session.turns[-1].observations:
                observation = state.session.turns[-1].observations[-1]
            else:
                observation = Observation(
                    tool_name=tool_name,
                    success=False,
                    error="用户拒绝执行该 recipe。",
                    data={"error_kind": "permission_denied"},
                )
        if result.transition.next_mode:
            state.current_mode = result.transition.next_mode
        self._refresh_harness_state(state)
        with state.lock:
            state.status = "idle"
            state.updated_at = _utc_now()
            state.current_command_step_id = current_step["step_id"]
            state.current_command_step_index = current_step["step_index"]
        self._emit(
            event_handler,
            "turn_end",
            state.session.session_id,
            {
                "turn_id": turn_id,
                "final_text": "",
                "termination_reason": result.transition.reason,
                "turns_used": result.turns_used,
                "max_turns": self.max_turns,
                "error": result.transition.message or "",
            },
        )
        self._persist_state(state)
        self._notify_status(event_handler, state)
        return observation

    def _emit_plan_updated(
        self,
        event_handler: Optional[EventHandler],
        state: ManagedSession,
        plan: PlanSnapshot,
    ) -> None:
        self._emit_with_snapshot(
            event_handler,
            "plan_updated",
            state,
            {"plan": self._plan_to_dict(plan)},
        )

    def _plan_to_dict(self, plan: PlanSnapshot) -> Dict[str, Any]:
        return {
            "session_id": plan.session_id,
            "title": plan.title,
            "content": plan.content,
            "updated_at": plan.updated_at,
            "workflow_state": plan.workflow_state,
            "path": plan.path,
            "summary": plan.summary,
        }
