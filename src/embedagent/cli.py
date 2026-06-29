from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional

from embedagent.hosted.launch_config import LaunchOverrides, resolve_launch_config
from embedagent.hosted.runtime import create_hosted_runtime
from embedagent.llm import ModelClientError
from embedagent.modes import DEFAULT_MODE, initialize_modes, parse_mode_command
from embedagent.tui import TUIUnavailableError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EmbedAgent Phase 6A In-Process CLI。")
    parser.add_argument(
        "message",
        nargs="*",
        help="要发送给 Agent 的用户消息。",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="模型服务根地址。示例：http://127.0.0.1:8000/v1",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="模型服务 API Key。示例：sk-local",
    )
    parser.add_argument(
        "--model",
        default="",
        help="模型名称。示例：qwen3.5-coder",
    )
    parser.add_argument(
        "--workspace",
        default=os.getcwd(),
        help="工作区根目录。示例：D:/Claude-project/ccode-win7",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="请求模型的超时时间（秒）。示例：120",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Optional model/tool loop safety limit; omit for open continuation",
    )
    parser.add_argument(
        "--mode",
        default=None,
        help="初始工作模式。示例：build；恢复会话时默认沿用摘要中的模式。",
    )
    parser.add_argument(
        "--resume",
        default="",
        help="恢复一个会话，可传 session_id、latest 或 summary.json 路径。示例：--resume latest",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="列出最近可恢复的会话摘要。",
    )
    parser.add_argument(
        "--session-limit",
        type=int,
        default=10,
        help="列出会话时返回的最大条数。示例：10",
    )
    parser.add_argument(
        "--approve-all",
        action="store_true",
        help="自动批准所有需要确认的操作。",
    )
    parser.add_argument(
        "--approve-writes",
        action="store_true",
        help="自动批准文件写入操作。",
    )
    parser.add_argument(
        "--approve-commands",
        action="store_true",
        help="自动批准命令和工具链执行操作。",
    )
    parser.add_argument(
        "--permission-rules",
        default="",
        help="权限规则文件路径，相对于工作区或绝对路径。示例：.embedagent/permission-rules.json",
    )
    parser.add_argument(
        "--max-context-tokens",
        type=int,
        default=None,
        help="覆盖上下文窗口大小（token 数）。示例：32000",
    )
    parser.add_argument(
        "--reserve-output-tokens",
        type=int,
        default=None,
        help="覆盖为输出预留的 token 数。示例：3000",
    )
    parser.add_argument(
        "--chars-per-token",
        type=float,
        default=None,
        help="覆盖字符/token 估算比率。示例：3.0",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="禁用流式输出，等待完整回复后再打印。",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="启动最小 TUI 原型。若依赖未安装，会给出提示。",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="启动 PyWebView GUI 前端。若依赖未安装，会给出提示。",
    )
    return parser


def _read_user_message(parts: List[str], prompt: str = "user> ") -> str:
    if parts:
        return " ".join(parts).strip()
    return input(prompt).strip()


def _format_session_record(item: Dict[str, object]) -> str:
    goal = str(item.get("user_goal") or item.get("summary_text") or "").strip()
    if len(goal) > 80:
        goal = goal[:80] + "..."
    return "{session_id}  mode={mode}  updated={updated}  goal={goal}".format(
        session_id=str(item.get("session_id") or ""),
        mode=str(item.get("current_mode") or ""),
        updated=str(item.get("updated_at") or ""),
        goal=goal,
    )


def _parse_initial_message(
    parser: argparse.ArgumentParser,
    raw_message: str,
    fallback_mode: str,
) -> List[str]:
    try:
        initial_mode, user_message, switched = parse_mode_command(
            raw_message,
            fallback_mode=fallback_mode,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return [initial_mode, user_message, "1" if switched else "0"]


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = os.path.realpath(args.workspace)
    initialize_modes(workspace)

    try:
        launch_config = resolve_launch_config(
            workspace,
            LaunchOverrides(
                base_url=args.base_url,
                api_key=args.api_key,
                model=args.model,
                timeout=args.timeout,
                max_turns=args.max_turns,
                approve_all=args.approve_all,
                approve_writes=args.approve_writes,
                approve_commands=args.approve_commands,
                permission_rules=args.permission_rules,
                max_context_tokens=args.max_context_tokens,
                reserve_output_tokens=args.reserve_output_tokens,
                chars_per_token=args.chars_per_token,
            ),
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.list_sessions:
        runtime = create_hosted_runtime(launch_config)
        sessions = runtime.session_host.list_sessions(limit=max(1, int(args.session_limit)))
        if not sessions:
            sys.stdout.write("当前没有可恢复的会话摘要。\n")
            return 0
        for item in sessions:
            sys.stdout.write(_format_session_record(item) + "\n")
        return 0

    resumed_summary = None  # type: Optional[Dict[str, object]]
    fallback_mode = (
        args.mode or getattr(launch_config.app_config, "default_mode", None) or DEFAULT_MODE
    )
    if args.resume:
        try:
            runtime = create_hosted_runtime(launch_config)
            resumed_summary = runtime.session_host.load_session_summary(args.resume)
        except ValueError as exc:
            parser.error(str(exc))
        fallback_mode = args.mode or str(resumed_summary.get("current_mode") or DEFAULT_MODE)

    if args.tui:
        initial_mode = fallback_mode
        initial_message = " ".join(args.message).strip()
        switched = False
        if initial_message:
            parsed = _parse_initial_message(parser, initial_message, fallback_mode)
            initial_mode = parsed[0]
            initial_message = parsed[1]
            switched = parsed[2] == "1"
        if switched and not initial_message:
            initial_message = ""
        try:
            from embedagent.frontend.tui.launcher import launch_tui

            return launch_tui(
                workspace=workspace,
                mode=initial_mode,
                resume=args.resume,
                message=initial_message,
                base_url=args.base_url or None,
                api_key=args.api_key or None,
                model=args.model or None,
                timeout=args.timeout,
                max_turns=args.max_turns,
                approve_all=args.approve_all,
                approve_writes=args.approve_writes,
                approve_commands=args.approve_commands,
                permission_rules=args.permission_rules,
            )
        except TUIUnavailableError as exc:
            sys.stderr.write("error: %s\n" % exc)
            return 1

    if args.gui:
        initial_mode = fallback_mode
        initial_message = " ".join(args.message).strip()
        if initial_message:
            parsed = _parse_initial_message(parser, initial_message, fallback_mode)
            initial_mode = parsed[0]
            initial_message = parsed[1]
        try:
            from embedagent.frontend.gui.launcher import launch_gui

            launch_gui(
                workspace=workspace,
                mode=initial_mode,
                debug=False,
                headless=False,
                base_url=args.base_url or None,
                api_key=args.api_key or None,
                model=args.model or None,
                timeout=args.timeout,
                max_turns=args.max_turns,
                approve_all=args.approve_all,
                approve_writes=args.approve_writes,
                approve_commands=args.approve_commands,
                permission_rules=args.permission_rules,
            )
            return 0
        except (ImportError, RuntimeError, ValueError) as exc:
            sys.stderr.write("error: %s\n" % exc)
            return 1

    raw_prompt = "resume> " if resumed_summary is not None else "user> "
    raw_message = _read_user_message(args.message, prompt=raw_prompt)
    if not raw_message:
        parser.error("必须提供用户消息。")

    parsed = _parse_initial_message(parser, raw_message, fallback_mode)
    initial_mode = parsed[0]
    user_message = parsed[1]
    switched = parsed[2] == "1"

    if switched and not user_message:
        sys.stdout.write("已切换到 %s 模式。\n" % initial_mode)
        return 0

    runtime_state = {
        "printed": False,
        "final_text": "",
        "last_error": "",
    }

    def on_event(event_name: str, session_id: str, payload: Dict[str, object]) -> None:
        if event_name == "assistant_delta":
            text = str(payload.get("text") or "")
            if not args.no_stream and text:
                sys.stdout.write(text)
                sys.stdout.flush()
                runtime_state["printed"] = True
            return
        if event_name == "tool_started":
            if runtime_state["printed"]:
                sys.stdout.write("\n")
                sys.stdout.flush()
                runtime_state["printed"] = False
            sys.stderr.write(
                "[tool] %s %s\n"
                % (
                    str(payload.get("tool_name") or ""),
                    payload.get("arguments"),
                )
            )
            sys.stderr.flush()
            return
        if event_name == "tool_finished":
            sys.stderr.write(
                "[observation] %s success=%s\n"
                % (
                    str(payload.get("tool_name") or ""),
                    bool(payload.get("success")),
                )
            )
            sys.stderr.flush()
            return
        if event_name == "permission_required":
            permission = payload.get("permission") or {}
            if not isinstance(permission, dict):
                return
            details = permission.get("details") or {}
            summary = (
                str((details.get("path") or details.get("command") or ""))
                if isinstance(details, dict)
                else ""
            )
            if len(summary) > 120:
                summary = summary[:120] + "..."
            sys.stderr.write(
                "[permission] %s %s %s\n"
                % (
                    str(permission.get("category") or ""),
                    str(permission.get("tool_name") or ""),
                    summary,
                )
            )
            sys.stderr.flush()
            return
        if event_name == "user_input_required":
            return
        if event_name == "session_resumed":
            sys.stderr.write("[resume] session=%s\n" % session_id)
            sys.stderr.flush()
            return
        if event_name == "command_result":
            message = str(payload.get("message") or "")
            if message:
                sys.stdout.write(message + ("\n" if not message.endswith("\n") else ""))
                sys.stdout.flush()
                runtime_state["printed"] = True
            return
        if event_name == "plan_updated":
            plan = payload.get("plan") or {}
            title = (
                str(plan.get("title") or "Current Plan")
                if isinstance(plan, dict)
                else "Current Plan"
            )
            sys.stderr.write("[plan] updated %s\n" % title)
            sys.stderr.flush()
            return
        if event_name == "context_compacted":
            return
        if event_name == "session_finished":
            runtime_state["final_text"] = str(payload.get("final_text") or "")
            return
        if event_name == "session_error":
            runtime_state["last_error"] = str(payload.get("error") or "")
            return

    runtime = create_hosted_runtime(launch_config, event_handler=on_event)
    session_host = runtime.session_host

    try:
        if args.resume:
            snapshot = session_host.resume_session(
                args.resume, initial_mode, event_handler=on_event
            )
        else:
            snapshot = session_host.create_session(initial_mode, event_handler=on_event)
    except ValueError as exc:
        parser.error(str(exc))

    def permission_resolver(ticket: Dict[str, object]) -> bool:
        reason = str(ticket.get("reason") or "该操作需要确认。")
        sys.stderr.write("%s [y/N]: " % reason)
        sys.stderr.flush()
        answer = input().strip().lower()
        return answer in ("y", "yes")

    def user_input_resolver(ticket: Dict[str, object]) -> Dict[str, object]:
        question = str(ticket.get("question") or "请输入回答。")
        options = ticket.get("options") if isinstance(ticket.get("options"), list) else []
        sys.stderr.write(question + "\n")
        for item in options:
            if not isinstance(item, dict):
                continue
            suffix = " -> %s" % item.get("mode") if item.get("mode") else ""
            sys.stderr.write(
                "  %s. %s%s\n" % (item.get("index") or "-", item.get("text") or "", suffix)
            )
        sys.stderr.write("answer> ")
        sys.stderr.flush()
        raw = input().strip()
        if raw.isdigit():
            for item in options:
                if not isinstance(item, dict):
                    continue
                if int(item.get("index") or 0) != int(raw):
                    continue
                return {
                    "answer": str(item.get("text") or ""),
                    "selected_index": int(item.get("index") or 0),
                    "selected_mode": str(item.get("mode") or ""),
                    "selected_option_text": str(item.get("text") or ""),
                }
        return {"answer": raw}

    try:
        session_host.submit_user_message(
            session_id=str(snapshot.get("session_id") or ""),
            text=user_message,
            stream=not args.no_stream,
            wait=True,
            permission_resolver=permission_resolver,
            user_input_resolver=user_input_resolver,
            event_handler=on_event,
        )
    except (ModelClientError, RuntimeError, ValueError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1

    final_text = runtime_state["final_text"]
    if runtime_state["last_error"]:
        sys.stderr.write("error: %s\n" % runtime_state["last_error"])
        return 1
    if args.no_stream:
        sys.stdout.write(final_text)
    if final_text and not final_text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
