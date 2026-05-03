from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TerminalTheme:
    vertical: str = "|"
    horizontal: str = "-"
    prompt_user: str = "user> "
    prompt_confirm: str = "confirm(y/n)> "


DIFF_THEMES = {
    "dark": {
        "addition_bg": "#0d2818",
        "addition_fg": "#4ade80",
        "deletion_bg": "#3f0f0f",
        "deletion_fg": "#f87171",
        "line_number": "#6b7280",
        "gutter": "#374151",
        "hunk_header": "#1e40af",
    },
    "light": {
        "addition_bg": "#dcfce7",
        "addition_fg": "#166534",
        "deletion_bg": "#fee2e2",
        "deletion_fg": "#991b1b",
        "line_number": "#9ca3af",
        "gutter": "#e5e7eb",
        "hunk_header": "#dbeafe",
    },
}


def default_theme():
    return TerminalTheme()


def get_diff_theme(theme_name="dark"):
    """Get diff color theme by name.

    Args:
        theme_name: Theme name ("dark" or "light")

    Returns:
        Dict with color values for diff rendering
    """
    return DIFF_THEMES.get(theme_name, DIFF_THEMES["dark"])
