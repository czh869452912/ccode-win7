"""
EmbedAgent GUI Frontend
PyWebView + FastAPI 实现
"""


def launch_gui(*args, **kwargs):
    """Lazy entry-point wrapper — defers pywebview import until call time."""
    from .launcher import launch_gui as _real
    return _real(*args, **kwargs)
