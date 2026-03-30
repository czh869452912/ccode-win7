from embedagent.frontend.tui.bootstrap import TUIUnavailableError, run_tui

__all__ = ["TerminalApp", "EmbedAgentTUI", "TUIUnavailableError", "run_tui"]


def __getattr__(name):
    if name in ("TerminalApp", "EmbedAgentTUI"):
        from embedagent.frontend.tui.app import TerminalApp
        return TerminalApp
    raise AttributeError(name)
