from __future__ import annotations

import fnmatch
import io
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent.artifacts import ArtifactStore
from embedagent.session import Observation


MAX_READ_CHARS = 40000
MAX_LIST_RESULTS = 500
MAX_SEARCH_MATCHES = 100
MAX_COMMAND_OUTPUT_CHARS = 40000
MAX_DIAGNOSTICS = 200
MAX_INLINE_ARTIFACT_TEXT_CHARS = 1600
MAX_INLINE_COMMAND_PREVIEW_CHARS = 1200
MAX_INLINE_LIST_ITEMS = 20
MAX_INLINE_LIST_CHARS = 3000
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


class ToolContext(object):
    """Shared workspace helpers injected into every tool module via build_tools(ctx)."""

    def __init__(self, workspace: str, artifact_store: ArtifactStore) -> None:
        self.workspace = workspace
        self.artifact_store = artifact_store

    # ------------------------------------------------------------------ paths

    def resolve_path(self, path: str, allow_missing: bool = False) -> str:
        if not path:
            raise ToolError("路径不能为空。")
        candidate = path if os.path.isabs(path) else os.path.join(self.workspace, path)
        resolved = os.path.realpath(candidate)
        workspace_norm = os.path.normcase(self.workspace)
        resolved_norm = os.path.normcase(resolved)
        if not (
            resolved_norm == workspace_norm
            or resolved_norm.startswith(workspace_norm + os.sep)
        ):
            raise ToolError("路径超出当前工作区。")
        if not allow_missing and not os.path.exists(resolved):
            raise ToolError("路径不存在：%s" % path)
        return resolved

    def resolve_directory(self, path: str) -> str:
        resolved = self.resolve_path(path)
        if not os.path.isdir(resolved):
            raise ToolError("路径不是目录：%s" % path)
        return resolved

    def relative_path(self, path: str) -> str:
        relative = os.path.relpath(path, self.workspace)
        if relative == ".":
            return "."
        return relative.replace(os.sep, "/")

    # ------------------------------------------------------------ text I/O

    def normalize_newlines(self, content: str) -> str:
        return content.replace("\r\n", "\n").replace("\r", "\n")

    def detect_newline(self, raw_content: str) -> str:
        if "\r\n" in raw_content:
            return "\r\n"
        if "\r" in raw_content:
            return "\r"
        return "\n"

    def is_binary_file(self, path: str) -> bool:
        with io.open(path, "rb") as handle:
            sample = handle.read(2048)
        return b"\x00" in sample

    def read_text(self, path: str) -> Tuple[str, str, str]:
        with io.open(path, "rb") as handle:
            raw_bytes = handle.read()
        if b"\x00" in raw_bytes:
            raise ToolError("文件看起来不是文本文件。")
        last_error = None
        for encoding in TEXT_ENCODINGS:
            try:
                raw_content = raw_bytes.decode(encoding)
                return (
                    self.normalize_newlines(raw_content),
                    self.detect_newline(raw_content),
                    encoding,
                )
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ToolError("文件编码无法识别：%s" % last_error)

    def write_text(self, path: str, content: str, newline_style: str, encoding: str) -> None:
        serialized = content.replace("\n", newline_style)
        with io.open(path, "w", encoding=encoding, newline="") as handle:
            handle.write(serialized)

    def preview_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...[artifact preview truncated]"

    # -------------------------------------------------------- file iteration

    def iter_files(self, root: str, pattern: Optional[str]) -> List[str]:
        if os.path.isfile(root):
            return [root]
        collected = []
        for current_root, dir_names, file_names in os.walk(root):
            dir_names[:] = [name for name in dir_names if name not in SKIP_DIR_NAMES]
            for file_name in file_names:
                absolute_path = os.path.join(current_root, file_name)
                relative = self.relative_path(absolute_path)
                if pattern and not (
                    fnmatch.fnmatch(file_name, pattern)
                    or fnmatch.fnmatch(relative, pattern)
                ):
                    continue
                collected.append(absolute_path)
        collected.sort()
        return collected

    # ------------------------------------------------------- output shrinking

    def shrink_text_field(
        self,
        tool_name: str,
        data: Dict[str, Any],
        field_name: str,
        inline_limit: int,
    ) -> None:
        value = data.get(field_name)
        if not isinstance(value, str):
            return
        sanitized = self.artifact_store.sanitize_text(value)
        data[field_name + "_char_count"] = len(sanitized)
        if len(sanitized) <= inline_limit:
            data[field_name] = sanitized
            return
        data[field_name] = self.preview_text(sanitized, inline_limit)
        data[field_name + "_artifact_ref"] = self.artifact_store.write_text(
            tool_name,
            field_name,
            sanitized,
            metadata={"char_count": len(sanitized)},
        )

    def shrink_list_field(
        self,
        tool_name: str,
        data: Dict[str, Any],
        field_name: str,
        inline_items: int,
    ) -> None:
        value = data.get(field_name)
        if not isinstance(value, list):
            return
        sanitized = self.artifact_store.sanitize_jsonable(value)
        serialized = json.dumps(sanitized, ensure_ascii=False)
        if len(sanitized) <= inline_items and len(serialized) <= MAX_INLINE_LIST_CHARS:
            data[field_name] = sanitized
            return
        data[field_name] = sanitized[:inline_items]
        data[field_name + "_item_count"] = len(sanitized)
        data[field_name + "_artifact_ref"] = self.artifact_store.write_json(
            tool_name,
            field_name,
            sanitized,
            metadata={"item_count": len(sanitized)},
        )

    def shrink_observation(self, observation: Observation) -> Observation:
        if not isinstance(observation.data, dict):
            return observation
        data = dict(observation.data)
        self.shrink_text_field(observation.tool_name, data, "content", MAX_INLINE_ARTIFACT_TEXT_CHARS)
        self.shrink_text_field(observation.tool_name, data, "stdout", MAX_INLINE_COMMAND_PREVIEW_CHARS)
        self.shrink_text_field(observation.tool_name, data, "stderr", MAX_INLINE_COMMAND_PREVIEW_CHARS)
        self.shrink_text_field(observation.tool_name, data, "diff", MAX_INLINE_COMMAND_PREVIEW_CHARS)
        self.shrink_list_field(observation.tool_name, data, "diagnostics", MAX_INLINE_LIST_ITEMS)
        self.shrink_list_field(observation.tool_name, data, "files", MAX_INLINE_LIST_ITEMS)
        self.shrink_list_field(observation.tool_name, data, "matches", MAX_INLINE_LIST_ITEMS)
        self.shrink_list_field(observation.tool_name, data, "entries", MAX_INLINE_LIST_ITEMS)
        observation.data = data
        return observation

    # --------------------------------------------------- process execution

    def truncate_output(self, text: str) -> Tuple[str, bool]:
        if len(text) <= MAX_COMMAND_OUTPUT_CHARS:
            return text, False
        return text[:MAX_COMMAND_OUTPUT_CHARS], True

    def bundled_toolchain_root(self) -> Optional[str]:
        env_root = os.environ.get("EMBEDAGENT_LLVM_ROOT", "").strip()
        candidates = []
        if env_root:
            candidates.append(os.path.realpath(env_root))
        candidates.append(os.path.join(self.workspace, "toolchains", "llvm", "current"))
        for candidate in candidates:
            if os.path.isdir(os.path.join(candidate, "bin")):
                return candidate
        return None

    def build_process_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        root = self.bundled_toolchain_root()
        if not root:
            return env
        prepend = []
        for subdir in ("bin", "libexec"):
            full = os.path.join(root, subdir)
            if os.path.isdir(full):
                prepend.append(full)
        if prepend:
            current_path = env.get("PATH", "")
            env["EMBEDAGENT_LLVM_ROOT"] = root
            env["PATH"] = os.pathsep.join(prepend + ([current_path] if current_path else []))
        return env

    def terminate_process_tree(self, process: subprocess.Popen) -> None:
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

    def run_subprocess(
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
            env=self.build_process_env(),
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            self.terminate_process_tree(process)
            stdout, stderr = process.communicate()
        duration_ms = int((time.time() - started) * 1000)
        stdout, stdout_truncated = self.truncate_output(stdout or "")
        stderr, stderr_truncated = self.truncate_output(stderr or "")
        return {
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "duration_ms": duration_ms,
            "timed_out": timed_out,
        }

    def build_command_observation(
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
        toolchain_root = self.bundled_toolchain_root()
        data = {
            "command": command_text,
            "cwd": self.relative_path(cwd),
            "exit_code": result["exit_code"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "stdout_truncated": result["stdout_truncated"],
            "stderr_truncated": result["stderr_truncated"],
            "duration_ms": result["duration_ms"],
            "timed_out": result["timed_out"],
            "toolchain_root": self.relative_path(toolchain_root) if toolchain_root else None,
        }
        return Observation(tool_name=tool_name, success=success, error=error, data=data)

    def build_diagnostic_observation(
        self,
        tool_name: str,
        command_text: str,
        cwd: str,
        result: Dict[str, Any],
    ) -> Observation:
        observation = self.build_command_observation(tool_name, command_text, cwd, result)
        combined = (result["stdout"] or "") + "\n" + (result["stderr"] or "")
        diagnostics = self.parse_diagnostics(combined)
        observation.data.update(self.diagnostic_counts(diagnostics))
        observation.data.update({"diagnostics": diagnostics, "diagnostic_count": len(diagnostics)})
        return observation

    def run_shell_tool(
        self,
        tool_name: str,
        command_text: str,
        cwd_argument: str,
        timeout_sec: int,
        diagnostic: bool = False,
    ) -> Observation:
        if not command_text:
            raise ToolError("命令不能为空。")
        cwd = self.resolve_directory(cwd_argument)
        if timeout_sec <= 0:
            raise ToolError("timeout_sec 必须大于 0。")
        result = self.run_subprocess(command=command_text, cwd=cwd, timeout_sec=timeout_sec, shell=True)
        if diagnostic:
            return self.build_diagnostic_observation(tool_name, command_text, cwd, result)
        return self.build_command_observation(tool_name, command_text, cwd, result)

    # ----------------------------------------------------------- git helpers

    def git_relative_arg(self, path: str) -> Optional[str]:
        resolved = self.resolve_path(path)
        relative = self.relative_path(resolved)
        if relative == ".":
            return None
        return relative

    def run_git_command(self, args: List[str]) -> Dict[str, Any]:
        return self.run_subprocess(
            command=args,
            cwd=self.workspace,
            timeout_sec=DEFAULT_COMMAND_TIMEOUT_SEC,
            shell=False,
        )

    # ------------------------------------------------- diagnostic parsing

    def normalize_level(self, level: str) -> str:
        return "error" if level == "fatal error" else level

    def parse_diagnostics(self, text: str) -> List[Dict[str, Any]]:
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
                    "level": self.normalize_level(match.group("level")),
                    "message": match.group("message").strip(),
                }
            )
            if len(diagnostics) >= MAX_DIAGNOSTICS:
                break
        return diagnostics

    def diagnostic_counts(self, diagnostics: List[Dict[str, Any]]) -> Dict[str, int]:
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

    def extract_first_int(self, patterns: List[str], text: str) -> int:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0

    def parse_test_summary(self, text: str) -> Dict[str, int]:
        passed = self.extract_first_int([
            r"(\d+)\s+tests?\s+passed",
            r"(\d+)\s+passed",
            r"passed[:=]\s*(\d+)",
        ], text)
        failed = self.extract_first_int([
            r"(\d+)\s+tests?\s+failed",
            r"(\d+)\s+failed",
            r"failures?[:=]\s*(\d+)",
        ], text)
        skipped = self.extract_first_int([
            r"(\d+)\s+tests?\s+skipped",
            r"(\d+)\s+skipped",
            r"skipped[:=]\s*(\d+)",
        ], text)
        total = passed + failed + skipped
        return {"passed": passed, "failed": failed, "skipped": skipped, "total": total}

    def parse_coverage_summary(self, text: str) -> Dict[str, Optional[float]]:
        metrics = {
            "line_coverage": None,
            "function_coverage": None,
            "branch_coverage": None,
            "region_coverage": None,
        }  # type: Dict[str, Optional[float]]
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
        if any(value is None for value in metrics.values()):
            for line in text.splitlines():
                if not line.strip().startswith("TOTAL"):
                    continue
                percentages = [token for token in line.split() if token.endswith("%")]
                if len(percentages) >= 3:
                    metrics["region_coverage"] = metrics["region_coverage"] or float(percentages[0][:-1])
                    metrics["function_coverage"] = metrics["function_coverage"] or float(percentages[1][:-1])
                    metrics["line_coverage"] = metrics["line_coverage"] or float(percentages[2][:-1])
                    if len(percentages) >= 4:
                        metrics["branch_coverage"] = metrics["branch_coverage"] or float(percentages[3][:-1])
                break
        return metrics
