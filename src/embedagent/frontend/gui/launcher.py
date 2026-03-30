"""
EmbedAgent GUI Launcher
启动 PyWebView + FastAPI 后端
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, Optional

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


def _resolve_runtime_value(override: Any, configured: Any, default: Any) -> Any:
    if override is not None:
        if isinstance(override, str):
            if override.strip():
                return override
        else:
            return override
    if configured is not None:
        return configured
    return default


def create_core(workspace: str, config: Optional[Dict[str, Any]] = None):
    """创建 Agent Core 实例"""
    # 延迟导入以避免循环依赖
    from embedagent.core.adapter import AgentCoreAdapter
    from embedagent.context import ContextManager, make_context_config
    from embedagent.llm import OpenAICompatibleClient
    from embedagent.config import load_config
    from embedagent.permissions import PermissionPolicy
    from embedagent.project_memory import ProjectMemoryStore
    from embedagent.tools import ToolRuntime

    options = dict(config or {})
    workspace = os.path.realpath(workspace)
    
    # 加载配置
    app_config = load_config(workspace)
    base_url = str(_resolve_runtime_value(options.get("base_url"), app_config.base_url, "http://127.0.0.1:8000/v1"))
    api_key = str(_resolve_runtime_value(options.get("api_key"), app_config.api_key, ""))
    model = str(_resolve_runtime_value(options.get("model"), app_config.model, ""))
    timeout = float(_resolve_runtime_value(options.get("timeout"), app_config.timeout, 120.0))
    max_turns = int(_resolve_runtime_value(options.get("max_turns"), app_config.max_turns, 8))
    permission_rules = str(options.get("permission_rules") or "")
    if not model:
        raise ValueError("必须通过 --model 或配置文件提供模型名称。")
    
    # 创建 LLM 客户端
    client = OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
    )
    
    # 创建工具运行时
    tools = ToolRuntime(workspace=workspace, app_config=app_config)
    context_manager = ContextManager(
        config=make_context_config(app_config),
        project_memory=ProjectMemoryStore(workspace),
    )
    permission_policy = PermissionPolicy(
        auto_approve_all=bool(options.get("approve_all", False)),
        auto_approve_writes=bool(options.get("approve_writes", False)),
        auto_approve_commands=bool(options.get("approve_commands", False)),
        workspace=workspace,
        rules_path=permission_rules,
    )
    
    # 创建 Core Adapter
    core = AgentCoreAdapter(workspace=workspace, config=options)
    core.initialize(
        client=client,
        tools=tools,
        max_turns=max_turns,
        permission_policy=permission_policy,
        context_manager=context_manager,
    )
    
    return core


def _detect_windows_renderer() -> Dict[str, Any]:
    if sys.platform != "win32":
        return {"platform": sys.platform, "renderer": "non-win32"}
    try:
        import webview.platforms.winforms as winforms
        return {
            "platform": "win32",
            "renderer": str(getattr(winforms, "renderer", "unknown")),
            "is_chromium": bool(getattr(winforms, "is_chromium", False)),
        }
    except Exception as exc:
        return {
            "platform": "win32",
            "renderer": "unknown",
            "error": str(exc),
        }


def _bundle_root() -> str:
    env_root = os.environ.get("EMBEDAGENT_BUNDLE_ROOT", "").strip()
    if env_root:
        return os.path.realpath(env_root)
    candidate = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    return candidate


def _bundled_webview2_runtime() -> str:
    override = os.environ.get("EMBEDAGENT_WEBVIEW2_RUNTIME", "").strip()
    candidates = []
    if override:
        candidates.append(override)
    root = _bundle_root()
    candidates.extend(
        [
            os.path.join(root, "runtime", "webview2-fixed-runtime"),
            os.path.join(root, "runtime", "webview2"),
            os.path.join(root, "bin", "webview2-fixed-runtime"),
            os.path.join(root, "bin", "webview2"),
        ]
    )
    for candidate in candidates:
        resolved = os.path.realpath(candidate)
        if not os.path.isdir(resolved):
            continue
        executable = os.path.join(resolved, "msedgewebview2.exe")
        if os.path.isfile(executable):
            return resolved
    return ""


def _running_from_bundle() -> bool:
    root = _bundle_root()
    return (
        os.path.isdir(os.path.join(root, "runtime"))
        and os.path.isdir(os.path.join(root, "app"))
    )


def _configure_webview_runtime() -> Dict[str, Any]:
    import webview

    runtime_path = _bundled_webview2_runtime()
    source = "system"
    if runtime_path:
        webview.settings["WEBVIEW2_RUNTIME_PATH"] = runtime_path
        source = "bundle"
    try:
        import webview.platforms.winforms as winforms
    except Exception as exc:
        raise RuntimeError("无法初始化 Windows WebView 引擎：%s" % exc)

    is_chromium = False
    detector = getattr(winforms, "_is_chromium", None)
    if callable(detector):
        try:
            is_chromium = bool(detector())
        except Exception:
            is_chromium = bool(getattr(winforms, "is_chromium", False))
    else:
        is_chromium = bool(getattr(winforms, "is_chromium", False))
    renderer = str(getattr(winforms, "renderer", "unknown"))
    if runtime_path and renderer != "edgechromium":
        raise RuntimeError(
            "已找到 bundle 内 WebView2 运行时，但 pywebview 未进入 edgechromium。"
            "请改用 TUI/CLI，或检查 Fixed Version 运行时目录。"
        )
    if _running_from_bundle() and not runtime_path:
        raise RuntimeError(
            "未找到 bundle 内 Fixed Version WebView2 109。"
            "当前 GUI 不再静默回退到 IE11，请改用 TUI/CLI，或补齐运行时。"
        )
    if not is_chromium or renderer != "edgechromium":
        raise RuntimeError(
            "当前环境没有可用的 Chromium WebView。"
            "GUI 不再回退到 IE11，请改用 TUI/CLI。"
        )
    return {
        "runtime_path": runtime_path,
        "runtime_source": source,
        "bundle_required": _running_from_bundle(),
    }


def _write_renderer_report(path: str, report: Dict[str, Any]) -> None:
    if not path:
        return
    target = os.path.realpath(path)
    parent = os.path.dirname(target)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)


def launch_gui(
    workspace: str,
    host: str = "127.0.0.1",
    port: int = 0,  # 0 表示自动选择端口
    mode: str = "code",
    debug: bool = False,
    headless: bool = False,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    max_turns: Optional[int] = None,
    approve_all: bool = False,
    approve_writes: bool = False,
    approve_commands: bool = False,
    permission_rules: str = "",
    auto_close_seconds: Optional[float] = None,
    renderer_report: str = "",
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
        raise RuntimeError("GUI 依赖未安装。")
    
    import uvicorn
    import webview
    workspace = os.path.realpath(workspace)
    runtime_info = _configure_webview_runtime() if sys.platform == "win32" else {
        "runtime_path": "",
        "runtime_source": "non-win32",
        "bundle_required": False,
    }
    
    # 查找可用端口
    if port == 0:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, 0))
        port = sock.getsockname()[1]
        sock.close()
    
    # 创建 Core
    _LOGGER.info(f"Initializing Agent Core for workspace: {workspace}")
    core = create_core(
        workspace,
        {
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "timeout": timeout,
            "max_turns": max_turns,
            "approve_all": approve_all,
            "approve_writes": approve_writes,
            "approve_commands": approve_commands,
            "permission_rules": permission_rules,
        },
    )
    
    try:
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

        renderer_info = _detect_windows_renderer()
        renderer_info.update(runtime_info)
        _LOGGER.info("GUI renderer detection: %s", renderer_info.get("renderer"))
        _write_renderer_report(renderer_report, renderer_info)
        
        # 等待服务器启动
        _LOGGER.info(f"Starting server at {server_url}")
        time.sleep(1)
        
        if headless:
            _LOGGER.info("Running in headless mode, press Ctrl+C to exit")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return
        
        # 创建 PyWebView 窗口
        window_title = f"EmbedAgent - {os.path.basename(workspace)}"
        
        # Windows 7 兼容性设置
        webview_settings = {
            "text_select": True,
            "confirm_close": True,
        }

        window = webview.create_window(
            title=window_title,
            url=server_url,
            width=1400,
            height=900,
            min_size=(800, 600),
            **webview_settings
        )
        
        _LOGGER.info("Starting GUI...")
        if auto_close_seconds and auto_close_seconds > 0:
            def close_after_delay() -> None:
                time.sleep(float(auto_close_seconds))
                try:
                    window.destroy()
                except Exception as exc:
                    _LOGGER.warning("Failed to auto-close GUI window: %s", exc)

            webview.start(close_after_delay, debug=debug)
        else:
            webview.start(debug=debug)
    finally:
        _LOGGER.info("Shutting down...")
        core.shutdown()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EmbedAgent GUI")
    parser.add_argument("workspace", nargs="?", help="Workspace directory")
    parser.add_argument("--workspace", dest="workspace_option", default="", help="Workspace directory")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=0, help="Server port (0=auto)")
    parser.add_argument("--mode", default="code", help="Initial mode")
    parser.add_argument("--base-url", default="", help="Model service root URL")
    parser.add_argument("--api-key", default="", help="Model service API key")
    parser.add_argument("--model", default="", help="Model name")
    parser.add_argument("--timeout", type=float, default=None, help="Model request timeout in seconds")
    parser.add_argument("--max-turns", type=int, default=None, help="Maximum turns per session")
    parser.add_argument("--approve-all", action="store_true", help="Auto-approve all risky actions")
    parser.add_argument("--approve-writes", action="store_true", help="Auto-approve file writes")
    parser.add_argument("--approve-commands", action="store_true", help="Auto-approve commands and toolchain runs")
    parser.add_argument("--permission-rules", default="", help="Permission rules file path")
    parser.add_argument("--auto-close-seconds", type=float, default=None, help="Auto-close GUI window after N seconds")
    parser.add_argument("--renderer-report", default="", help="Optional path to write renderer detection JSON")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--headless", action="store_true", help="Headless mode (no window)")
    return parser


def main(argv: Optional[list] = None) -> int:
    """命令行入口"""
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace_arg = args.workspace_option or args.workspace or os.getcwd()

    # 验证工作区
    workspace = os.path.abspath(workspace_arg)
    if not os.path.isdir(workspace):
        _LOGGER.error(f"Workspace not found: {workspace}")
        return 1

    try:
        launch_gui(
            workspace=workspace,
            host=args.host,
            port=args.port,
            mode=args.mode,
            debug=args.debug,
            headless=args.headless,
            base_url=args.base_url or None,
            api_key=args.api_key or None,
            model=args.model or None,
            timeout=args.timeout,
            max_turns=args.max_turns,
            approve_all=args.approve_all,
            approve_writes=args.approve_writes,
            approve_commands=args.approve_commands,
            permission_rules=args.permission_rules,
            auto_close_seconds=args.auto_close_seconds,
            renderer_report=args.renderer_report,
        )
    except (RuntimeError, ValueError) as exc:
        _LOGGER.error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
