from __future__ import annotations

import fnmatch
import io
import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent.session import Observation


MAX_READ_CHARS = 40000
MAX_LIST_RESULTS = 500
MAX_SEARCH_MATCHES = 100
MAX_COMMAND_OUTPUT_CHARS = 40000
MAX_DIAGNOSTICS = 200
DEFAULT_COMMAND_TIMEOUT_SEC = 30
DEFAULT_BUILD_TIMEOUT_SEC = 120
TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "cp936")
SKIP_DIR_NAMES = {".git", ".hg", ".svn", "__pycache__"}
CLANG_DIAGNOSTIC_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?P<column>\d+): (?P<level>fatal error|error|warning|note): (?P<message>.*)$"
)
MSVC_DIAGNOSTIC_RE = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+)(?:,(?P<column>\d+))?\): (?P<level>fatal error|error|warning|note) [A-Z0-9]+: (?P<message>.*)$"
)


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
        return [
            "read_file",
            "list_files",
            "search_text",
            "edit_file",
            "run_command",
            "git_status",
            "git_diff",
            "git_log",
            "compile_project",
            "run_tests",
            "run_clang_tidy",
            "run_clang_analyzer",
            "collect_coverage",
            "report_quality",
        ]

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
            "run_command": ToolDefinition(
                name="run_command",
                description="执行工作区内的 shell 命令。用于构建、运行脚本或采集终端结果。命令在项目工作区或其子目录中执行。",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的命令文本，按系统 shell 语法书写。示例：git status --short",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "命令执行目录，相对于项目根目录。示例：.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "description": "命令超时时间，单位为秒。示例：30",
                        },
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
                handler=self._run_command,
            ),
            "git_status": ToolDefinition(
                name="git_status",
                description="查看当前 Git 工作区状态。用于确认分支、未提交修改和未跟踪文件。路径必须位于当前仓库内。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要查看的仓库路径或子路径，相对于项目根目录。示例：.",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
                handler=self._git_status,
            ),
            "git_diff": ToolDefinition(
                name="git_diff",
                description="查看 Git 差异内容。用于检查未提交修改或已暂存修改的具体文本差异。路径必须位于当前仓库内。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要查看的仓库路径或子路径，相对于项目根目录。示例：.",
                        },
                        "scope": {
                            "type": "string",
                            "enum": ["working", "staged"],
                            "description": "差异范围，working 表示工作区，staged 表示已暂存。示例：working",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
                handler=self._git_diff,
            ),
            "git_log": ToolDefinition(
                name="git_log",
                description="查看最近的 Git 提交历史。用于了解最近改动、作者和提交主题。路径必须位于当前仓库内。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要查看的仓库路径或子路径，相对于项目根目录。示例：.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "要返回的提交条数，默认 10。示例：5",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
                handler=self._git_log,
            ),
            "compile_project": ToolDefinition(
                name="compile_project",
                description="执行项目编译命令。用于构建目标程序并解析编译诊断。命令应输出可解析的编译器信息。",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的编译命令文本。示例：clang -Wall -Wextra src/main.c -o build/main.exe",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "编译执行目录，相对于项目根目录。示例：.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "description": "编译超时时间，单位为秒。示例：120",
                        },
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
                handler=self._compile_project,
            ),
            "run_tests": ToolDefinition(
                name="run_tests",
                description="执行测试命令并汇总结果。用于运行单元测试、集成测试或测试驱动脚本。命令应输出可统计的测试结果。",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的测试命令文本。示例：ctest --output-on-failure",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "测试执行目录，相对于项目根目录。示例：build",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "description": "测试超时时间，单位为秒。示例：120",
                        },
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
                handler=self._run_tests,
            ),
            "run_clang_tidy": ToolDefinition(
                name="run_clang_tidy",
                description="执行 clang-tidy 检查命令。用于收集静态检查警告和错误。命令应输出 clang 风格诊断。",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的 clang-tidy 命令文本。示例：clang-tidy src/main.c -- -Iinclude",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "检查执行目录，相对于项目根目录。示例：.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "description": "检查超时时间，单位为秒。示例：120",
                        },
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
                handler=self._run_clang_tidy,
            ),
            "run_clang_analyzer": ToolDefinition(
                name="run_clang_analyzer",
                description="执行 clang 静态分析命令。用于收集分析器发现的问题和定位信息。命令应输出 clang 风格诊断。",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的静态分析命令文本。示例：clang --analyze src/main.c -Iinclude",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "分析执行目录，相对于项目根目录。示例：.",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "description": "分析超时时间，单位为秒。示例：120",
                        },
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
                handler=self._run_clang_analyzer,
            ),
            "collect_coverage": ToolDefinition(
                name="collect_coverage",
                description="执行覆盖率收集命令。用于汇总覆盖率报告并提取核心百分比。命令应输出可识别的覆盖率文本。",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "要执行的覆盖率命令文本。示例：llvm-cov report build/app.exe -instr-profile=default.profdata",
                        },
                        "cwd": {
                            "type": "string",
                            "description": "覆盖率执行目录，相对于项目根目录。示例：build",
                        },
                        "timeout_sec": {
                            "type": "integer",
                            "description": "覆盖率命令超时时间，单位为秒。示例：120",
                        },
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
                handler=self._collect_coverage,
            ),
            "report_quality": ToolDefinition(
                name="report_quality",
                description="评估当前质量门结果。用于根据错误数、失败测试和覆盖率判断是否通过。参数应来自前置工具 Observation。",
                parameters={
                    "type": "object",
                    "properties": {
                        "error_count": {
                            "type": "integer",
                            "description": "当前累计错误数。示例：0",
                        },
                        "test_failures": {
                            "type": "integer",
                            "description": "当前失败测试数。示例：0",
                        },
                        "warning_count": {
                            "type": "integer",
                            "description": "当前累计警告数，未传时按 0 处理。示例：3",
                        },
                        "line_coverage": {
                            "type": "number",
                            "description": "当前语句或行覆盖率百分比。示例：85.5",
                        },
                        "min_line_coverage": {
                            "type": "number",
                            "description": "最低可接受的行覆盖率百分比。示例：80.0",
                        },
                    },
                    "required": ["error_count", "test_failures"],
                    "additionalProperties": False,
                },
                handler=self._report_quality,
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

    def _resolve_directory(self, path: str) -> str:
        resolved = self._resolve_path(path)
        if not os.path.isdir(resolved):
            raise ToolError("路径不是目录：%s" % path)
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

    def _truncate_output(self, text: str) -> Tuple[str, bool]:
        if len(text) <= MAX_COMMAND_OUTPUT_CHARS:
            return text, False
        return text[:MAX_COMMAND_OUTPUT_CHARS], True

    def _normalize_level(self, level: str) -> str:
        return "error" if level == "fatal error" else level

    def _parse_diagnostics(self, text: str) -> List[Dict[str, Any]]:
        diagnostics = []
        for line in text.splitlines():
            match = CLANG_DIAGNOSTIC_RE.match(line) or MSVC_DIAGNOSTIC_RE.match(line)
            if not match:
                continue
            diagnostics.append(
                {
                    "file": match.group("file"),
                    "line": int(match.group("line")),
                    "column": int(match.groupdict().get("column") or 1),
                    "level": self._normalize_level(match.group("level")),
                    "message": match.group("message").strip(),
                }
            )
            if len(diagnostics) >= MAX_DIAGNOSTICS:
                break
        return diagnostics

    def _diagnostic_counts(self, diagnostics: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {"error_count": 0, "warning_count": 0, "note_count": 0}
        for item in diagnostics:
            level = item["level"]
            if level == "error":
                counts["error_count"] += 1
            elif level == "warning":
                counts["warning_count"] += 1
            elif level == "note":
                counts["note_count"] += 1
        return counts

    def _extract_first_int(self, patterns: List[str], text: str) -> int:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0

    def _parse_test_summary(self, text: str) -> Dict[str, int]:
        passed = self._extract_first_int([
            r"(\d+)\s+tests?\s+passed",
            r"(\d+)\s+passed",
            r"passed[:=]\s*(\d+)",
        ], text)
        failed = self._extract_first_int([
            r"(\d+)\s+tests?\s+failed",
            r"(\d+)\s+failed",
            r"failures?[:=]\s*(\d+)",
        ], text)
        skipped = self._extract_first_int([
            r"(\d+)\s+tests?\s+skipped",
            r"(\d+)\s+skipped",
            r"skipped[:=]\s*(\d+)",
        ], text)
        total = passed + failed + skipped
        return {"passed": passed, "failed": failed, "skipped": skipped, "total": total}

    def _parse_coverage_summary(self, text: str) -> Dict[str, Optional[float]]:
        metrics = {
            "line_coverage": None,
            "function_coverage": None,
            "branch_coverage": None,
            "region_coverage": None,
        }
        patterns = {
            "line_coverage": [r"lines?[^\d\n]*([0-9]+(?:\.[0-9]+)?)%", r"line coverage[^\d\n]*([0-9]+(?:\.[0-9]+)?)%"],
            "function_coverage": [r"functions?[^\d\n]*([0-9]+(?:\.[0-9]+)?)%", r"function coverage[^\d\n]*([0-9]+(?:\.[0-9]+)?)%"],
            "branch_coverage": [r"branches?[^\d\n]*([0-9]+(?:\.[0-9]+)?)%", r"branch coverage[^\d\n]*([0-9]+(?:\.[0-9]+)?)%"],
            "region_coverage": [r"regions?[^\d\n]*([0-9]+(?:\.[0-9]+)?)%", r"region coverage[^\d\n]*([0-9]+(?:\.[0-9]+)?)%"],
        }
        for key, candidates in patterns.items():
            for pattern in candidates:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    metrics[key] = float(match.group(1))
                    break
        return metrics

    def _terminate_process_tree(self, process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return
        process.kill()

    def _run_subprocess(
        self,
        command: Any,
        cwd: str,
        timeout_sec: int,
        shell: bool,
    ) -> Dict[str, Any]:
        started = time.time()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate_process_tree(process)
            stdout, stderr = process.communicate()
        duration_ms = int((time.time() - started) * 1000)
        stdout, stdout_truncated = self._truncate_output(stdout or "")
        stderr, stderr_truncated = self._truncate_output(stderr or "")
        return {
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
        }

    def _build_command_observation(
        self,
        tool_name: str,
        command_text: str,
        cwd: str,
        result: Dict[str, Any],
    ) -> Observation:
        success = (result["exit_code"] == 0) and (not result["timed_out"])
        error = None
        if result["timed_out"]:
            error = "命令执行超时，已强制终止。"
        elif result["exit_code"] != 0:
            error = "命令退出码为 %s。" % result["exit_code"]
        data = {
            "command": command_text,
            "cwd": self._relative_path(cwd),
            "exit_code": result["exit_code"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "stdout_truncated": result["stdout_truncated"],
            "stderr_truncated": result["stderr_truncated"],
            "duration_ms": result["duration_ms"],
            "timed_out": result["timed_out"],
        }
        return Observation(tool_name=tool_name, success=success, error=error, data=data)

    def _build_diagnostic_observation(
        self,
        tool_name: str,
        command_text: str,
        cwd: str,
        result: Dict[str, Any],
    ) -> Observation:
        observation = self._build_command_observation(tool_name, command_text, cwd, result)
        combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
        diagnostics = self._parse_diagnostics(combined)
        observation.data.update(self._diagnostic_counts(diagnostics))
        observation.data.update({"diagnostics": diagnostics, "diagnostic_count": len(diagnostics)})
        return observation

    def _run_shell_tool(
        self,
        tool_name: str,
        command_text: str,
        cwd_argument: str,
        timeout_sec: int,
        diagnostic: bool = False,
    ) -> Observation:
        if not command_text:
            raise ToolError("命令不能为空。")
        cwd = self._resolve_directory(cwd_argument)
        if timeout_sec <= 0:
            raise ToolError("timeout_sec 必须大于 0。")
        result = self._run_subprocess(command=command_text, cwd=cwd, timeout_sec=timeout_sec, shell=True)
        if diagnostic:
            return self._build_diagnostic_observation(tool_name, command_text, cwd, result)
        return self._build_command_observation(tool_name, command_text, cwd, result)

    def _git_relative_arg(self, path: str) -> Optional[str]:
        resolved = self._resolve_path(path)
        relative = self._relative_path(resolved)
        if relative == ".":
            return None
        return relative

    def _run_git_command(self, args: List[str]) -> Dict[str, Any]:
        return self._run_subprocess(command=args, cwd=self.workspace, timeout_sec=DEFAULT_COMMAND_TIMEOUT_SEC, shell=False)

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
                matches.append({"path": self._relative_path(file_path), "line": index, "text": line[:300]})
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

    def _run_command(self, arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments["command"]).strip()
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_COMMAND_TIMEOUT_SEC)
        return self._run_shell_tool("run_command", command_text, cwd_argument, timeout_sec)

    def _git_status(self, arguments: Dict[str, Any]) -> Observation:
        path_argument = str(arguments["path"])
        relative_arg = self._git_relative_arg(path_argument)
        command = ["git", "-C", self.workspace, "status", "--short", "--branch"]
        if relative_arg:
            command.extend(["--", relative_arg])
        result = self._run_git_command(command)
        observation = self._build_command_observation("git_status", " ".join(command), self.workspace, result)
        if not observation.success:
            return observation
        lines = [line for line in result["stdout"].splitlines() if line]
        branch = ""
        entries = []
        for line in lines:
            if line.startswith("## "):
                branch = line[3:].strip()
                continue
            status_code = line[:2]
            file_path = line[3:].strip() if len(line) > 3 else ""
            entries.append({"status": status_code, "path": file_path})
        observation.data.update({"path": path_argument, "branch": branch, "entries": entries})
        return observation

    def _git_diff(self, arguments: Dict[str, Any]) -> Observation:
        path_argument = str(arguments["path"])
        scope = str(arguments.get("scope") or "working")
        if scope not in ("working", "staged"):
            raise ToolError("scope 只能是 working 或 staged。")
        relative_arg = self._git_relative_arg(path_argument)
        command = ["git", "-C", self.workspace, "diff"]
        if scope == "staged":
            command.append("--cached")
        if relative_arg:
            command.extend(["--", relative_arg])
        result = self._run_git_command(command)
        observation = self._build_command_observation("git_diff", " ".join(command), self.workspace, result)
        if not observation.success:
            return observation
        diff_text = result["stdout"]
        observation.data.update({
            "path": path_argument,
            "scope": scope,
            "file_count": diff_text.count("diff --git "),
            "line_count": diff_text.count("\n") + (1 if diff_text else 0),
            "diff": diff_text,
        })
        return observation

    def _git_log(self, arguments: Dict[str, Any]) -> Observation:
        path_argument = str(arguments["path"])
        limit = int(arguments.get("limit") or 10)
        if limit <= 0:
            raise ToolError("limit 必须大于 0。")
        relative_arg = self._git_relative_arg(path_argument)
        command = [
            "git",
            "-C",
            self.workspace,
            "log",
            "--date=iso-strict",
            "--pretty=format:%H%x1f%an%x1f%ad%x1f%s%x1e",
            "-n",
            str(limit),
        ]
        if relative_arg:
            command.extend(["--", relative_arg])
        result = self._run_git_command(command)
        observation = self._build_command_observation("git_log", " ".join(command), self.workspace, result)
        if not observation.success:
            return observation
        entries = []
        for record in result["stdout"].split("\x1e"):
            record = record.strip()
            if not record:
                continue
            parts = record.split("\x1f")
            if len(parts) != 4:
                continue
            entries.append({"commit": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]})
        observation.data.update({"path": path_argument, "limit": limit, "entries": entries})
        return observation

    def _compile_project(self, arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments["command"]).strip()
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        return self._run_shell_tool("compile_project", command_text, cwd_argument, timeout_sec, diagnostic=True)

    def _run_tests(self, arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments["command"]).strip()
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        observation = self._run_shell_tool("run_tests", command_text, cwd_argument, timeout_sec, diagnostic=True)
        combined = (observation.data.get("stdout") or "") + "\n" + (observation.data.get("stderr") or "")
        observation.data.update({"test_summary": self._parse_test_summary(combined)})
        return observation

    def _run_clang_tidy(self, arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments["command"]).strip()
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        return self._run_shell_tool("run_clang_tidy", command_text, cwd_argument, timeout_sec, diagnostic=True)

    def _run_clang_analyzer(self, arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments["command"]).strip()
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        return self._run_shell_tool("run_clang_analyzer", command_text, cwd_argument, timeout_sec, diagnostic=True)

    def _collect_coverage(self, arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments["command"]).strip()
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        observation = self._run_shell_tool("collect_coverage", command_text, cwd_argument, timeout_sec)
        combined = (observation.data.get("stdout") or "") + "\n" + (observation.data.get("stderr") or "")
        observation.data.update({"coverage_summary": self._parse_coverage_summary(combined)})
        return observation

    def _report_quality(self, arguments: Dict[str, Any]) -> Observation:
        error_count = int(arguments.get("error_count") or 0)
        test_failures = int(arguments.get("test_failures") or 0)
        warning_count = int(arguments.get("warning_count") or 0)
        line_coverage = arguments.get("line_coverage")
        min_line_coverage = arguments.get("min_line_coverage")
        line_coverage_value = float(line_coverage) if line_coverage is not None else None
        min_line_coverage_value = float(min_line_coverage) if min_line_coverage is not None else None
        reasons = []
        if error_count > 0:
            reasons.append("存在 %s 个错误。" % error_count)
        if test_failures > 0:
            reasons.append("存在 %s 个失败测试。" % test_failures)
        if line_coverage_value is not None and min_line_coverage_value is not None and line_coverage_value < min_line_coverage_value:
            reasons.append("行覆盖率 %.2f%% 低于阈值 %.2f%%。" % (line_coverage_value, min_line_coverage_value))
        passed = not reasons
        data = {
            "passed": passed,
            "error_count": error_count,
            "warning_count": warning_count,
            "test_failures": test_failures,
            "line_coverage": line_coverage_value,
            "min_line_coverage": min_line_coverage_value,
            "reasons": reasons,
        }
        return Observation(
            tool_name="report_quality",
            success=passed,
            error=None if passed else "质量门未通过。",
            data=data,
        )
