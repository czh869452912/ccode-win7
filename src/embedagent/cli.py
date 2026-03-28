from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

from embedagent.llm import ModelClientError, OpenAICompatibleClient
from embedagent.loop import AgentLoop
from embedagent.modes import DEFAULT_MODE, parse_mode_command
from embedagent.permissions import PermissionPolicy, PermissionRequest
from embedagent.session import Action, Observation, Session
from embedagent.session_store import SessionSummaryStore
from embedagent.tools import ToolRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EmbedAgent Phase 5 质量保障 CLI。"
    )
    parser.add_argument(
        "message",
        nargs="*",
        help="要发送给 Agent 的用户消息。",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("EMBEDAGENT_BASE_URL", "http://127.0.0.1:8000/v1"),
        help="模型服务根地址。示例：http://127.0.0.1:8000/v1",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("EMBEDAGENT_API_KEY", ""),
        help="模型服务 API Key。示例：sk-local",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("EMBEDAGENT_MODEL", ""),
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
        default=float(os.environ.get("EMBEDAGENT_TIMEOUT", "120")),
        help="请求模型的超时时间（秒）。示例：120",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=8,
        help="单次会话允许的最大循环轮数。示例：8",
    )
    parser.add_argument(
        "--mode",
        default=None,
        help="初始工作模式。示例：code；恢复会话时默认沿用摘要中的模式。",
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
        "--no-stream",
        action="store_true",
        help="禁用流式输出，等待完整回复后再打印。",
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = os.path.realpath(args.workspace)
    summary_store = SessionSummaryStore(workspace)

    if args.list_sessions:
        sessions = summary_store.list_summaries(limit=max(1, int(args.session_limit)))
        if not sessions:
            sys.stdout.write("当前没有可恢复的会话摘要。\n")
            return 0
        for item in sessions:
            sys.stdout.write(_format_session_record(item) + "\n")
        return 0

    resumed_session = None  # type: Optional[Session]
    resumed_summary = None  # type: Optional[Dict[str, object]]
    fallback_mode = args.mode or DEFAULT_MODE
    if args.resume:
        try:
            resumed_summary = summary_store.load_summary(args.resume)
        except ValueError as exc:
            parser.error(str(exc))
        fallback_mode = args.mode or str(resumed_summary.get("current_mode") or DEFAULT_MODE)
        resumed_session = summary_store.create_resumed_session(resumed_summary, fallback_mode)

    raw_prompt = "resume> " if resumed_session is not None else "user> "
    raw_message = _read_user_message(args.message, prompt=raw_prompt)
    if not raw_message:
        parser.error("必须提供用户消息。")

    try:
        initial_mode, user_message, switched = parse_mode_command(
            raw_message,
            fallback_mode=fallback_mode,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if switched and not user_message:
        sys.stdout.write("已切换到 %s 模式。\n" % initial_mode)
        return 0

    if not args.model:
        parser.error("必须通过 --model 或 EMBEDAGENT_MODEL 提供模型名称。")

    client = OpenAICompatibleClient(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        timeout=args.timeout,
    )
    tools = ToolRuntime(workspace)
    permission_policy = PermissionPolicy(
        auto_approve_all=args.approve_all,
        auto_approve_writes=args.approve_writes,
        auto_approve_commands=args.approve_commands,
        workspace=workspace,
        rules_path=args.permission_rules,
    )
    loop = AgentLoop(
        client=client,
        tools=tools,
        max_turns=args.max_turns,
        permission_policy=permission_policy,
        summary_store=summary_store,
    )

    if resumed_summary is not None:
        sys.stderr.write(
            "[resume] session=%s mode=%s\n"
            % (
                resumed_summary.get("session_id") or "",
                fallback_mode,
            )
        )
        sys.stderr.flush()

    streaming_state = {"printed": False}

    def on_text_delta(text: str) -> None:
        if not text:
            return
        sys.stdout.write(text)
        sys.stdout.flush()
        streaming_state["printed"] = True

    def on_tool_start(action: Action) -> None:
        if streaming_state["printed"]:
            sys.stdout.write("\n")
            sys.stdout.flush()
            streaming_state["printed"] = False
        sys.stderr.write(
            "[tool] %s %s\n"
            % (
                action.name,
                json.dumps(action.arguments, ensure_ascii=False, sort_keys=True),
            )
        )
        sys.stderr.flush()

    def on_tool_finish(action: Action, observation: Observation) -> None:
        sys.stderr.write(
            "[observation] %s success=%s\n"
            % (action.name, observation.success)
        )
        sys.stderr.flush()

    def on_permission_request(request: PermissionRequest) -> bool:
        summary = request.details.get("path") or request.details.get("command") or ""
        if len(summary) > 120:
            summary = summary[:120] + "..."
        sys.stderr.write(
            "[permission] %s %s %s\n"
            % (request.category, request.tool_name, summary)
        )
        sys.stderr.write("%s [y/N]: " % request.reason)
        sys.stderr.flush()
        answer = input().strip().lower()
        return answer in ("y", "yes")

    try:
        final_text, _ = loop.run(
            user_text=user_message,
            stream=not args.no_stream,
            initial_mode=initial_mode,
            on_text_delta=on_text_delta,
            on_tool_start=on_tool_start,
            on_tool_finish=on_tool_finish,
            permission_handler=on_permission_request,
            session=resumed_session,
        )
    except (ModelClientError, RuntimeError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1

    if args.no_stream:
        sys.stdout.write(final_text)
    if final_text and not final_text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

