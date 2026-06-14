import difflib

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from embedagent.frontend.tui.theme import get_diff_theme


class DiffView(object):
    """Render unified diffs with line numbers, gutter markers, and syntax highlighting."""

    def __init__(self, theme="dark"):
        self.theme = theme
        self._diff_content = ""
        self._filename = ""
        self._language = ""
        self._theme_colors = get_diff_theme(theme)
        self._addition_style = "bold %s on %s" % (
            self._theme_colors["addition_fg"],
            self._theme_colors["addition_bg"],
        )
        self._deletion_style = "bold %s on %s" % (
            self._theme_colors["deletion_fg"],
            self._theme_colors["deletion_bg"],
        )
        self._line_number_style = self._theme_colors["line_number"]
        self._gutter_style = self._theme_colors["gutter"]
        self._hunk_header_style = self._theme_colors["hunk_header"]

    def set_diff(self, old_text, new_text, filename=""):
        """Compute and store unified diff."""
        self._filename = filename
        self._language = self._detect_language(filename)

        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="a/" + filename,
            tofile="b/" + filename,
            lineterm="",
        )
        self._diff_content = "".join(diff)

    def render(self):
        """Render the diff as rich output."""
        if not self._diff_content:
            return Panel("No diff to display", title="Diff")

        return self._render_rich_diff()

    def _render_rich_diff(self):
        """Render diff with line numbers and gutter markers."""
        lines = self._diff_content.splitlines()
        if not lines:
            return Panel("Empty diff", title="Diff")

        table = Table(show_header=False, box=None, padding=(0, 0))
        table.add_column("gutter", width=3, style=self._gutter_style)
        table.add_column("old_line", width=4, justify="right", style=self._line_number_style)
        table.add_column("new_line", width=4, justify="right", style=self._line_number_style)
        table.add_column("content", ratio=1)

        old_line_num = 0
        new_line_num = 0

        for line in lines:
            if line.startswith("@@"):
                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                try:
                    parts = line.split(" ")
                    old_info = parts[1].split(",")
                    new_info = parts[2].split(",")
                    old_line_num = int(old_info[0][1:])
                    new_line_num = int(new_info[0][1:])
                except (IndexError, ValueError):
                    pass
                table.add_row(
                    "",
                    "",
                    "",
                    Text(line, style="bold " + self._hunk_header_style),
                )
            elif line.startswith("-"):
                content = line[1:]
                table.add_row(
                    "-",
                    str(old_line_num),
                    "",
                    Text(content, style=self._deletion_style),
                )
                old_line_num += 1
            elif line.startswith("+"):
                content = line[1:]
                table.add_row(
                    "+",
                    "",
                    str(new_line_num),
                    Text(content, style=self._addition_style),
                )
                new_line_num += 1
            elif line.startswith(" "):
                content = line[1:]
                table.add_row(
                    " ",
                    str(old_line_num),
                    str(new_line_num),
                    Text(content),
                )
                old_line_num += 1
                new_line_num += 1
            else:
                # Header line
                table.add_row("", "", "", Text(line, style="bold"))

        return Panel(table, title="Diff: %s" % self._filename, border_style="blue")

    def _detect_language(self, filename):
        """Detect programming language from filename extension."""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        mapping = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "c": "c",
            "cpp": "cpp",
            "h": "c",
            "hpp": "cpp",
            "java": "java",
            "go": "go",
            "rs": "rust",
            "md": "markdown",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "html": "html",
            "css": "css",
        }
        return mapping.get(ext, "text")

    def render_inline(self, old_text, new_text, filename=""):
        """Render diff inline for embedding in timeline."""
        self.set_diff(old_text, new_text, filename)
        return self.render()
