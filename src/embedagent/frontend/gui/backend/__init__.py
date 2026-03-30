"""
EmbedAgent GUI Backend
FastAPI + WebSocket 服务器
"""
try:
    from embedagent.frontend.gui.backend.server import GUIBackend
    __all__ = ["GUIBackend"]
except ImportError:
    # FastAPI 未安装时提供占位符
    class GUIBackend:
        def __init__(self, *args, **kwargs):
            raise ImportError("FastAPI is required for GUI backend. Install with: pip install fastapi uvicorn")
    __all__ = ["GUIBackend"]
