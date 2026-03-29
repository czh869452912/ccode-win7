from embedagent.frontends.terminal.bootstrap import TUIUnavailableError, run_tui

__all__ = ["TerminalApp", "EmbedAgentTUI", "TUIUnavailableError", "run_tui"]


def __getattr__(name):
    if name in ("TerminalApp", "EmbedAgentTUI"):
        from embedagent.frontends.terminal.app import TerminalApp
        return TerminalApp
    raise AttributeError(name)
