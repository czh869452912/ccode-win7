from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExplorerItem:
    kind: str
    path: str
    label: str
    detail: str = ""


@dataclass
class ArtifactRow:
    path: str
    tool_name: str = ""
    field_name: str = ""
    kind: str = ""
    created_at: str = ""


@dataclass
class EditorBuffer:
    path: str = ""
    content: str = ""
    original_content: str = ""
    encoding: str = "utf-8"
    newline: str = "\n"
    dirty: bool = False
    created: bool = False
    file_mtime: float = 0.0
