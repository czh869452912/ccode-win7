from __future__ import annotations

import fnmatch
import io
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent.session import Observation


MAX_READ_CHARS = 40000
MAX_LIST_RESULTS = 500
MAX_SEARCH_MATCHES = 100
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "cp936")
SKIP_DIR_NAMES = {".git", ".hg", ".svn", "__pycache__"}


class ToolError(Exception):
    pass


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Observation]

    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRuntime(object):
    def __init__(self, workspace: str) -> None:
        self.workspace = os.path.realpath(workspace)
        self._tools = self._build_tools()

    def schemas(self) -> List[Dict[str, Any]]:
        return [self._tools[name].schema() for name in self._tool_order()]

    def execute(self, name: str, arguments: Dict[str, Any]) -> Observation:
        tool = self._tools.get(name)
        if tool is None:
            return Observation(
                tool_name=name,
                success=False,
                error="未找到对应工具。",
                data={},
            )
        try:
            if not isinstance(arguments, dict):
                raise ToolError("工具参数必须是对象。")
            observation = tool.handler(arguments)
        except ToolError as exc:
            return Observation(
                tool_name=name,
                success=False,
                error=str(exc),
                data={},
            )
        except Exception as exc:
            return Observation(
                tool_name=name,
                success=False,
                error="工具执行失败：%s" % exc,
                data={},
            )
        observation.tool_name = name
        return observation

    def _tool_order(self) -> List[str]:
        return ["read_file", "list_files", "search_text", "edit_file"]

    def _build_tools(self) -> Dict[str, ToolDefinition]:
        return {
            "read_file": ToolDefinition(
                name="read_file",
                description="读取单个文本文件内容。用于查看源码、配置或文档的当前状态。路径必须位于项目工作区内。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要读取的文件路径，相对于项目根目录。示例：README.md",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
                handler=self._read_file,
            ),
            "list_files": ToolDefinition(
                name="list_files",
                description="列出目录中的文件路径。用于快速了解项目结构或定位目标文件。路径必须位于项目工作区内。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要列出的目录路径，相对于项目根目录。示例：docs",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "要匹配的 glob 模式，留空表示不过滤。示例：*.md",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
                handler=self._list_files,
            ),
            "search_text": ToolDefinition(
                name="search_text",
                description="搜索工作区中的文本内容。用于查找符号、关键字或错误信息出现位置。路径必须位于项目工作区内。",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "要搜索的文本片段，默认按不区分大小写匹配。示例：OpenAICompatibleClient",
                        },
                        "path": {
                            "type": "string",
                            "description": "要搜索的目录路径，相对于项目根目录。示例：src/embedagent",
                        },
                    },
                    "required": ["query", "path"],
                    "additionalProperties": False,
                },
                handler=self._search_text,
            ),
            "edit_file": ToolDefinition(
                name="edit_file",
                description="修改文件中的指定文本片段。用于替换、插入或删除已存在的内容。路径必须位于项目工作区内。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要修改的文件路径，相对于项目根目录。示例：src/embedagent/loop.py",
                        },
                        "old_text": {
                            "type": "string",
                            "description": "要被替换的原始文本，必须与文件内容完全一致。示例：print('old')",
                        },
                        "new_text": {
                            "type": "string",
                            "description": "替换后的新文本，传入空字符串表示删除。示例：print('new')",
                        },
                    },
                    "required": ["path", "old_text", "new_text"],
                    "additionalProperties": False,
                },
                handler=self._edit_file,
            ),
        }

    def _resolve_path(self, path: str) -> str:
        if not path:
            raise ToolError("路径不能为空。")
        candidate = path
        if not os.path.isabs(candidate):
            candidate = os.path.join(self.workspace, path)
        resolved = os.path.realpath(candidate)
        workspace_norm = os.path.normcase(self.workspace)
        resolved_norm = os.path.normcase(resolved)
        if not (
            resolved_norm == workspace_norm
            or resolved_norm.startswith(workspace_norm + os.sep)
        ):
            raise ToolError("路径超出当前工作区。")
        if not os.path.exists(resolved):
            raise ToolError("路径不存在：%s" % path)
        return resolved

    def _relative_path(self, path: str) -> str:
        relative = os.path.relpath(path, self.workspace)
        if relative == ".":
            return "."
        return relative.replace(os.sep, "/")

    def _normalize_newlines(self, content: str) -> str:
        return content.replace("\r\n", "\n").replace("\r", "\n")

    def _detect_newline(self, raw_content: str) -> str:
        if "\r\n" in raw_content:
            return "\r\n"
        if "\r" in raw_content:
            return "\r"
        return "\n"

    def _is_binary_file(self, path: str) -> bool:
        with io.open(path, "rb") as handle:
            sample = handle.read(2048)
        return b"\x00" in sample

    def _read_text(self, path: str) -> Tuple[str, str, str]:
        with io.open(path, "rb") as handle:
            raw_bytes = handle.read()
        if b"\x00" in raw_bytes:
            raise ToolError("文件看起来不是文本文件。")
        last_error = None
        for encoding in TEXT_ENCODINGS:
            try:
                raw_content = raw_bytes.decode(encoding)
                return (
                    self._normalize_newlines(raw_content),
                    self._detect_newline(raw_content),
                    encoding,
                )
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ToolError("文件编码无法识别：%s" % last_error)

    def _write_text(
        self,
        path: str,
        content: str,
        newline_style: str,
        encoding: str,
    ) -> None:
        serialized = content.replace("\n", newline_style)
        with io.open(path, "w", encoding=encoding, newline="") as handle:
            handle.write(serialized)

    def _iter_files(self, root: str, pattern: Optional[str]) -> List[str]:
        if os.path.isfile(root):
            return [root]
        collected = []
        for current_root, dir_names, file_names in os.walk(root):
            dir_names[:] = [
                name for name in dir_names if name not in SKIP_DIR_NAMES
            ]
            for file_name in file_names:
                absolute_path = os.path.join(current_root, file_name)
                relative_path = self._relative_path(absolute_path)
                if pattern and not (
                    fnmatch.fnmatch(file_name, pattern)
                    or fnmatch.fnmatch(relative_path, pattern)
                ):
                    continue
                collected.append(absolute_path)
        collected.sort()
        return collected

    def _read_file(self, arguments: Dict[str, Any]) -> Observation:
        path = self._resolve_path(str(arguments["path"]))
        if not os.path.isfile(path):
            raise ToolError("只能读取文件，不能读取目录。")
        content, _, encoding = self._read_text(path)
        original_length = len(content)
        truncated = original_length > MAX_READ_CHARS
        if truncated:
            content = content[:MAX_READ_CHARS]
        data = {
            "path": self._relative_path(path),
            "encoding": encoding,
            "char_count": original_length,
            "line_count": content.count("\n") + (1 if content else 0),
            "truncated": truncated,
            "content": content,
        }
        return Observation(tool_name="read_file", success=True, error=None, data=data)

    def _list_files(self, arguments: Dict[str, Any]) -> Observation:
        path = self._resolve_path(str(arguments["path"]))
        pattern = arguments.get("pattern")
        pattern = str(pattern) if pattern else None
        files = self._iter_files(path, pattern)
        truncated = len(files) > MAX_LIST_RESULTS
        visible = files[:MAX_LIST_RESULTS]
        data = {
            "path": self._relative_path(path),
            "pattern": pattern,
            "count": len(files),
            "truncated": truncated,
            "files": [self._relative_path(item) for item in visible],
        }
        return Observation(tool_name="list_files", success=True, error=None, data=data)

    def _search_text(self, arguments: Dict[str, Any]) -> Observation:
        query = str(arguments["query"])
        path = self._resolve_path(str(arguments["path"]))
        if not query:
            raise ToolError("搜索文本不能为空。")
        matches = []
        lowered_query = query.lower()
        for file_path in self._iter_files(path, pattern=None):
            if self._is_binary_file(file_path):
                continue
            try:
                content, _, _ = self._read_text(file_path)
            except ToolError:
                continue
            for index, line in enumerate(content.split("\n"), start=1):
                if lowered_query not in line.lower():
                    continue
                matches.append(
                    {
                        "path": self._relative_path(file_path),
                        "line": index,
                        "text": line[:300],
                    }
                )
                if len(matches) >= MAX_SEARCH_MATCHES:
                    break
            if len(matches) >= MAX_SEARCH_MATCHES:
                break
        data = {
            "query": query,
            "path": self._relative_path(path),
            "match_count": len(matches),
            "truncated": len(matches) >= MAX_SEARCH_MATCHES,
            "matches": matches,
        }
        return Observation(tool_name="search_text", success=True, error=None, data=data)

    def _edit_file(self, arguments: Dict[str, Any]) -> Observation:
        path = self._resolve_path(str(arguments["path"]))
        if not os.path.isfile(path):
            raise ToolError("只能修改已存在的文本文件。")
        old_text = str(arguments["old_text"])
        new_text = str(arguments["new_text"])
        if not old_text:
            raise ToolError("old_text 不能为空。")
        content, newline_style, encoding = self._read_text(path)
        occurrence_count = content.count(old_text)
        if occurrence_count == 0:
            raise ToolError("文件中未找到要替换的原始文本。")
        if occurrence_count > 1:
            raise ToolError("原始文本出现了 %s 次，请提供更精确的片段。" % occurrence_count)
        updated = content.replace(old_text, new_text, 1)
        self._write_text(path, updated, newline_style, encoding)
        data = {
            "path": self._relative_path(path),
            "encoding": encoding,
            "replaced": True,
            "line_count": updated.count("\n") + (1 if updated else 0),
        }
        return Observation(tool_name="edit_file", success=True, error=None, data=data)
