"""
EmbedAgent GUI Launcher
启动 PyWebView + FastAPI 后端
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
_LOGGER = logging.getLogger(__name__)


def check_dependencies():
    """检查依赖是否安装"""
    try:
        import webview
    except ImportError:
        _LOGGER.error("pywebview not installed. Run: pip install pywebview")
        return False
    
    try:
        import fastapi
    except ImportError:
        _LOGGER.error("fastapi not installed. Run: pip install fastapi uvicorn")
        return False
    
    return True


def create_core(workspace: str, config: dict):
    """创建 Agent Core 实例"""
    # 延迟导入以避免循环依赖
    from embedagent.core.adapter import AgentCoreAdapter
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
        max_turns=config.get("max_turns", 8)
    )
    
    return core


def launch_gui(
    workspace: str,
    host: str = "127.0.0.1",
    port: int = 0,  # 0 表示自动选择端口
    mode: str = "code",
    debug: bool = False,
    headless: bool = False,
):
    """
    启动 GUI
    
    Args:
        workspace: 工作区路径
        host: 服务器主机
        port: 服务器端口，0 表示自动选择
        mode: 初始模式
        debug: 是否调试模式
        headless: 是否无窗口模式（用于测试）
    """
    if not check_dependencies():
        sys.exit(1)
    
    import uvicorn
    import webview
    
    # 查找可用端口
    if port == 0:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, 0))
        port = sock.getsockname()[1]
        sock.close()
    
    # 创建 Core
    _LOGGER.info(f"Initializing Agent Core for workspace: {workspace}")
    core = create_core(workspace, {"max_turns": 8})
    
    # 创建 GUI Backend
    static_dir = os.path.join(
        os.path.dirname(__file__),
        "static"
    )
    
    from embedagent.frontend.gui.backend.server import GUIBackend
    backend = GUIBackend(core=core, static_dir=static_dir)
    
    # 启动 FastAPI 服务器（在后台线程）
    server_url = f"http://{host}:{port}"
    
    def run_server():
        uvicorn.run(
            backend.app,
            host=host,
            port=port,
            log_level="warning" if not debug else "info"
        )
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # 等待服务器启动
    _LOGGER.info(f"Starting server at {server_url}")
    time.sleep(1)
    
    if headless:
        _LOGGER.info("Running in headless mode, press Ctrl+C to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            _LOGGER.info("Shutting down...")
        return
    
    # 创建 PyWebView 窗口
    window_title = f"EmbedAgent - {os.path.basename(workspace)}"
    
    # Windows 7 兼容性设置
    webview_settings = {
        "text_select": True,
        "confirm_close": True,
    }
    
    # 尝试使用 Edge Chromium（如果安装了 WebView2）
    if sys.platform == "win32":
        try:
            import webview.platforms.winforms
            # 优先使用 Edge Chromium
            webview.platforms.winforms.BUILTIN_BROWSER = 'edgechromium'
            _LOGGER.info("Using Edge Chromium (WebView2)")
        except:
            _LOGGER.info("Using default browser (IE11)")
    
    window = webview.create_window(
        title=window_title,
        url=server_url,
        width=1400,
        height=900,
        min_size=(800, 600),
        **webview_settings
    )
    
    _LOGGER.info("Starting GUI...")
    webview.start(debug=debug)
    
    # 清理
    _LOGGER.info("Shutting down...")
    core.shutdown()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="EmbedAgent GUI")
    parser.add_argument("workspace", help="Workspace directory")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=0, help="Server port (0=auto)")
    parser.add_argument("--mode", default="code", help="Initial mode")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--headless", action="store_true", help="Headless mode (no window)")
    
    args = parser.parse_args()
    
    # 验证工作区
    workspace = os.path.abspath(args.workspace)
    if not os.path.isdir(workspace):
        _LOGGER.error(f"Workspace not found: {workspace}")
        sys.exit(1)
    
    launch_gui(
        workspace=workspace,
        host=args.host,
        port=args.port,
        mode=args.mode,
        debug=args.debug,
        headless=args.headless,
    )


if __name__ == "__main__":
    main()
