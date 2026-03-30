"""
TUI Launcher
使用新架构启动 TUI
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from embedagent.core.adapter import AgentCoreAdapter
from embedagent.frontend.tui.app import TerminalApp
from embedagent.frontend.tui.frontend_adapter import TUIFrontend

_LOGGER = logging.getLogger(__name__)


def create_core(workspace: str, config: Optional[dict] = None):
    """创建 Agent Core 实例"""
    from embedagent.llm import OpenAICompatibleClient
    from embedagent.tools import ToolRuntime
    from embedagent.config import load_config
    
    # 加载配置
    app_config = load_config(workspace)
    
    # 创建 LLM 客户端
    client = OpenAICompatibleClient(
        base_url=app_config.get("llm", {}).get("base_url", "http://localhost:8000"),
        api_key=app_config.get("llm", {}).get("api_key", ""),
        model=app_config.get("llm", {}).get("model", "gpt-3.5-turbo"),
    )
    
    # 创建工具运行时
    tools = ToolRuntime(workspace=workspace)
    
    # 创建 Core Adapter
    core = AgentCoreAdapter(workspace=workspace, config=app_config)
    core.initialize(
        client=client,
        tools=tools,
        max_turns=config.get("max_turns", 8) if config else 8
    )
    
    return core


def launch_tui(
    workspace: str,
    mode: str = "code",
    resume: str = "",
    message: str = "",
    headless: bool = False,
    **kwargs
):
    """
    启动 TUI
    
    Args:
        workspace: 工作区路径
        mode: 初始模式
        resume: 恢复会话的引用
        message: 初始消息
        headless: 无头模式（用于测试）
    """
    _LOGGER.info(f"Starting TUI for workspace: {workspace}")
    
    # 创建 Core
    core = create_core(workspace, {"max_turns": kwargs.get("max_turns", 8)})
    
    # 创建 TUI App
    app = TerminalApp(
        adapter=core,  # 这里传递 core，但 TerminalApp 需要适配
        workspace=workspace,
        initial_mode=mode,
        resume_reference=resume,
        initial_message=message,
        headless=headless,
        create_pipe_input=kwargs.get("create_pipe_input"),
        dummy_output=kwargs.get("dummy_output"),
    )
    
    # 创建并注册前端适配器
    frontend = TUIFrontend(app)
    core.register_frontend(frontend)
    
    # 运行
    try:
        exit_code = app.run()
        return exit_code
    except KeyboardInterrupt:
        _LOGGER.info("Interrupted by user")
        return 0
    finally:
        core.shutdown()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="EmbedAgent TUI")
    parser.add_argument("workspace", nargs="?", default=".", help="Workspace directory")
    parser.add_argument("--mode", default="code", help="Initial mode")
    parser.add_argument("--resume", default="", help="Resume session reference")
    parser.add_argument("--message", "-m", default="", help="Initial message")
    parser.add_argument("--headless", action="store_true", help="Headless mode")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 验证工作区
    workspace = os.path.abspath(args.workspace)
    if not os.path.isdir(workspace):
        _LOGGER.error(f"Workspace not found: {workspace}")
        sys.exit(1)
    
    # 启动
    exit_code = launch_tui(
        workspace=workspace,
        mode=args.mode,
        resume=args.resume,
        message=args.message,
        headless=args.headless,
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
