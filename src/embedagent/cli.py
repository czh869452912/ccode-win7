from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from embedagent.llm import ModelClientError, OpenAICompatibleClient
from embedagent.loop import AgentLoop
from embedagent.modes import DEFAULT_MODE, parse_mode_command
from embedagent.session import Action, Observation
from embedagent.tools import ToolRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EmbedAgent Phase 3 模式化 CLI。"
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
        default=DEFAULT_MODE,
        help="初始工作模式。示例：code",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="禁用流式输出，等待完整回复后再打印。",
    )
    return parser


def _read_user_message(parts: List[str]) -> str:
    if parts:
        return " ".join(parts).strip()
    return input("user> ").strip()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    raw_message = _read_user_message(args.message)
    if not raw_message:
        parser.error("必须提供用户消息。")
    if not args.model:
        parser.error("必须通过 --model 或 EMBEDAGENT_MODEL 提供模型名称。")

    try:
        initial_mode, user_message, switched = parse_mode_command(
            raw_message,
            fallback_mode=args.mode,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if switched and not user_message:
        sys.stdout.write("已切换到 %s 模式。\n" % initial_mode)
        return 0

    client = OpenAICompatibleClient(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        timeout=args.timeout,
    )
    tools = ToolRuntime(args.workspace)
    loop = AgentLoop(client=client, tools=tools, max_turns=args.max_turns)

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

    try:
        final_text, _ = loop.run(
            user_text=user_message,
            stream=not args.no_stream,
            initial_mode=initial_mode,
            on_text_delta=on_text_delta,
            on_tool_start=on_tool_start,
            on_tool_finish=on_tool_finish,
        )
    except (ModelClientError, RuntimeError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1

    if args.no_stream:
        sys.stdout.write(final_text)
    if final_text and not final_text.endswith("\n"):
        sys.stdout.write("\n")
    return 0
