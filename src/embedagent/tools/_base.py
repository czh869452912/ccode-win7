from __future__ import annotations

import fnmatch
import io
import json
import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from embedagent.runtime_discovery import discover_bundle_root
from embedagent.session import Observation
from embedagent.workspace_recipes import list_workspace_recipes, resolve_workspace_recipe


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
MANAGED_RUNTIME_TOOL_KEYS = ("python", "git", "rg", "ctags", "llvm")
LLVM_EXECUTABLE_NAMES = frozenset(
    (
        "clang",
        "clang.exe",
        "clang++",
        "clang++.exe",
        "clang-cl",
        "clang-cl.exe",
        "clang-tidy",
        "clang-tidy.exe",
        "clang-analyzer",
        "clang-analyzer.bat",
        "llvm-profdata",
        "llvm-profdata.exe",
        "llvm-cov",
        "llvm-cov.exe",
    )
)
DIRECT_MANAGED_EXECUTABLES = {
    "git": "git",
    "git.exe": "git",
    "rg": "rg",
    "rg.exe": "rg",
    "ctags": "ctags",
    "ctags.exe": "ctags",
    "python": "python",
    "python.exe": "python",
}
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
    metadata: Dict[str, Any] = field(default_factory=dict)
    read_only: bool = False
    concurrency_safe: bool = False
    interrupt_behavior: str = "block"
    result_budget_policy: str = "default"
    activity_kind: str = "tool"
    context_priority: int = 50

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

    def __init__(self, workspace: str, app_config: Any = None) -> None:
        self.workspace = workspace
        self.app_config = app_config
        self._thread_local = threading.local()
        self._bundle_root_cache = None  # type: Optional[str]
        self._bundle_root_resolved = False

    def set_interrupt_event(self, stop_event: Optional[threading.Event]) -> None:
        self._thread_local.stop_event = stop_event

    def clear_interrupt_event(self) -> None:
        if hasattr(self._thread_local, "stop_event"):
            delattr(self._thread_local, "stop_event")

    def get_interrupt_event(self) -> Optional[threading.Event]:
        return getattr(self._thread_local, "stop_event", None)

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

    def display_path(self, path: Optional[str]) -> str:
        if not path:
            return ""
        resolved = os.path.realpath(path)
        workspace_norm = os.path.normcase(self.workspace)
        resolved_norm = os.path.normcase(resolved)
        if resolved_norm == workspace_norm or resolved_norm.startswith(workspace_norm + os.sep):
            return self.relative_path(resolved)
        return resolved

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
        return text[:limit] + "\n...[stored preview truncated]"

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

    # --------------------------------------------------- process execution

    def truncate_output(self, text: str) -> Tuple[str, bool]:
        if len(text) <= MAX_COMMAND_OUTPUT_CHARS:
            return text, False
        return text[:MAX_COMMAND_OUTPUT_CHARS], True

    def allow_system_tool_fallback(self) -> bool:
        env_value = os.environ.get("EMBEDAGENT_ALLOW_SYSTEM_TOOL_FALLBACK", "").strip().lower()
        if env_value in ("1", "true", "yes", "on"):
            return True
        if env_value in ("0", "false", "no", "off"):
            return False
        configured = getattr(self.app_config, "allow_system_tool_fallback", None)
        return bool(configured)

    def bundle_root(self) -> Optional[str]:
        if not self._bundle_root_resolved:
            self._bundle_root_cache = discover_bundle_root(
                env_root=os.environ.get("EMBEDAGENT_BUNDLE_ROOT", "").strip(),
                anchor_path=__file__,
                anchor_levels=(3,),
            )
            self._bundle_root_resolved = True
        return self._bundle_root_cache

    def _llvm_root_candidates(self) -> List[Tuple[str, str]]:
        candidates = []  # type: List[Tuple[str, str]]
        env_root = os.environ.get("EMBEDAGENT_LLVM_ROOT", "").strip()
        if env_root:
            candidates.append((os.path.realpath(env_root), "bundle" if self.bundle_root() else "workspace"))
        bundle_root = self.bundle_root()
        if bundle_root:
            candidates.append((os.path.join(bundle_root, "bin", "llvm"), "bundle"))
        candidates.append((os.path.join(self.workspace, "toolchains", "llvm", "current"), "workspace"))
        candidates.append((os.path.join(self.workspace, "bin", "llvm"), "workspace"))
        return candidates

    def bundled_toolchain_root(self) -> Optional[str]:
        root, _ = self.resolve_managed_tool_path("llvm")
        return root

    def _managed_tool_candidates(self, tool_key: str) -> List[Tuple[str, str]]:
        bundle_root = self.bundle_root()
        candidates = []  # type: List[Tuple[str, str]]
        if tool_key == "llvm":
            return self._llvm_root_candidates()
        if tool_key == "python":
            if bundle_root:
                candidates.append((os.path.join(bundle_root, "runtime", "python", "python.exe"), "bundle"))
            candidates.append((os.path.join(self.workspace, "runtime", "python", "python.exe"), "workspace"))
            return candidates
        if tool_key == "git":
            if bundle_root:
                candidates.append((os.path.join(bundle_root, "bin", "git", "cmd", "git.exe"), "bundle"))
                candidates.append((os.path.join(bundle_root, "bin", "git", "bin", "git.exe"), "bundle"))
            candidates.append((os.path.join(self.workspace, "bin", "git", "cmd", "git.exe"), "workspace"))
            candidates.append((os.path.join(self.workspace, "bin", "git", "bin", "git.exe"), "workspace"))
            return candidates
        if tool_key == "rg":
            if bundle_root:
                candidates.append((os.path.join(bundle_root, "bin", "rg", "rg.exe"), "bundle"))
            candidates.append((os.path.join(self.workspace, "bin", "rg", "rg.exe"), "workspace"))
            return candidates
        if tool_key == "ctags":
            if bundle_root:
                candidates.append((os.path.join(bundle_root, "bin", "ctags", "ctags.exe"), "bundle"))
            candidates.append((os.path.join(self.workspace, "bin", "ctags", "ctags.exe"), "workspace"))
            return candidates
        return candidates

    def resolve_managed_tool_path(self, tool_key: str) -> Tuple[Optional[str], str]:
        for candidate, source in self._managed_tool_candidates(tool_key):
            if tool_key == "llvm":
                if os.path.isdir(os.path.join(candidate, "bin")):
                    return os.path.realpath(candidate), source
                continue
            if os.path.isfile(candidate):
                return os.path.realpath(candidate), source
        return None, ""

    def classify_managed_command(self, command_name: str) -> str:
        normalized = os.path.basename(str(command_name or "")).strip().lower()
        if normalized in DIRECT_MANAGED_EXECUTABLES:
            return DIRECT_MANAGED_EXECUTABLES[normalized]
        if normalized in LLVM_EXECUTABLE_NAMES:
            return "llvm"
        return ""

    def resolve_managed_command_executable(self, command_name: str, required: bool = True) -> Tuple[str, str]:
        tool_key = self.classify_managed_command(command_name)
        if not tool_key:
            return command_name, "system"
        path, source = self.resolve_managed_tool_path(tool_key)
        if tool_key == "llvm" and path:
            executable = os.path.join(path, "bin", os.path.basename(command_name))
            if os.path.isfile(executable):
                return executable, source
        elif path:
            return path, source
        if self.allow_system_tool_fallback():
            return command_name, "system"
        if required:
            raise ToolError("未找到托管工具：%s。当前环境未允许回退到系统 PATH。" % command_name)
        return command_name, "system"

    def managed_search_path_entries(self) -> List[str]:
        entries = []  # type: List[str]
        seen = set()
        git_exe, _ = self.resolve_managed_tool_path("git")
        if git_exe:
            git_dir = os.path.dirname(git_exe)
            sibling_bin = os.path.join(os.path.dirname(git_dir), "bin")
            for candidate in (git_dir, sibling_bin):
                if candidate and os.path.isdir(candidate):
                    resolved = os.path.realpath(candidate)
                    if resolved not in seen:
                        entries.append(resolved)
                        seen.add(resolved)
        for tool_key in ("rg", "ctags", "python"):
            executable, _ = self.resolve_managed_tool_path(tool_key)
            if executable:
                directory = os.path.dirname(executable)
                if os.path.isdir(directory):
                    resolved = os.path.realpath(directory)
                    if resolved not in seen:
                        entries.append(resolved)
                        seen.add(resolved)
        llvm_root, _ = self.resolve_managed_tool_path("llvm")
        if llvm_root:
            for candidate in (os.path.join(llvm_root, "bin"), os.path.join(llvm_root, "libexec")):
                if os.path.isdir(candidate):
                    resolved = os.path.realpath(candidate)
                    if resolved not in seen:
                        entries.append(resolved)
                        seen.add(resolved)
        return entries

    def runtime_environment_snapshot(self) -> Dict[str, Any]:
        resolved_tool_roots = {
            "bundle_root": "",
            "python_exe": "",
            "git_exe": "",
            "rg_exe": "",
            "ctags_exe": "",
            "llvm_root": "",
        }
        tool_sources = {}  # type: Dict[str, str]
        fallback_warnings = []  # type: List[str]
        for tool_key in MANAGED_RUNTIME_TOOL_KEYS:
            path, source = self.resolve_managed_tool_path(tool_key)
            if path:
                tool_sources[tool_key] = source
                if tool_key == "python":
                    resolved_tool_roots["python_exe"] = self.display_path(path)
                elif tool_key == "git":
                    resolved_tool_roots["git_exe"] = self.display_path(path)
                elif tool_key == "rg":
                    resolved_tool_roots["rg_exe"] = self.display_path(path)
                elif tool_key == "ctags":
                    resolved_tool_roots["ctags_exe"] = self.display_path(path)
                elif tool_key == "llvm":
                    resolved_tool_roots["llvm_root"] = self.display_path(path)
            elif self.bundle_root():
                fallback_warnings.append("Bundle 未包含必需工具：%s" % tool_key)
            elif not self.allow_system_tool_fallback():
                fallback_warnings.append("未找到托管工具：%s，且未启用系统回退。" % tool_key)
        bundle_root = self.bundle_root()
        if bundle_root:
            resolved_tool_roots["bundle_root"] = self.display_path(bundle_root)
            runtime_source = "bundle"
        elif any(source == "workspace" for source in tool_sources.values()):
            runtime_source = "workspace"
        elif self.allow_system_tool_fallback():
            runtime_source = "system"
        else:
            runtime_source = "unavailable"
        bundled_tools_ready = all(tool_sources.get(key) in ("bundle", "workspace") for key in ("git", "rg", "ctags", "llvm"))
        return {
            "runtime_source": runtime_source,
            "bundled_tools_ready": bundled_tools_ready,
            "fallback_warnings": fallback_warnings,
            "resolved_tool_roots": resolved_tool_roots,
            "tool_sources": tool_sources,
            "allow_system_tool_fallback": self.allow_system_tool_fallback(),
        }

    def list_workspace_recipes(self) -> Dict[str, Any]:
        return list_workspace_recipes(self.workspace)

    def resolve_workspace_recipe(
        self,
        recipe_id: str,
        expected_tool_name: str = "",
        target: str = "",
        profile: str = "",
    ) -> Dict[str, Any]:
        try:
            return resolve_workspace_recipe(
                self.workspace,
                recipe_id=recipe_id,
                expected_tool_name=expected_tool_name,
                target=target,
                profile=profile,
            )
        except ValueError as exc:
            raise ToolError(str(exc))

    def rewrite_command_for_managed_tools(self, command_text: str) -> Tuple[str, str, str]:
        match = re.match(r'^(\s*)(?:"([^"]+)"|([^\s|&;<>]+))', command_text)
        if not match:
            return command_text, "", ""
        leading = match.group(1) or ""
        token = match.group(2) or match.group(3) or ""
        tool_key = self.classify_managed_command(token)
        if not tool_key:
            return command_text, "", ""
        executable, source = self.resolve_managed_command_executable(token)
        rewritten = leading + '"' + executable + '"' + command_text[match.end():]
        return rewritten, tool_key, source

    def build_process_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        runtime = self.runtime_environment_snapshot()
        prepend = self.managed_search_path_entries()
        if prepend:
            current_path = env.get("PATH", "")
            llvm_root, _ = self.resolve_managed_tool_path("llvm")
            if llvm_root:
                env["EMBEDAGENT_LLVM_ROOT"] = llvm_root
            env["EMBEDAGENT_RUNTIME_SOURCE"] = str(runtime.get("runtime_source") or "")
            env["PATH"] = os.pathsep.join(prepend + ([current_path] if current_path else []))
        return env

    def terminate_process_tree(self, process: subprocess.Popen, grace_sec: float = 0.5) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
            if ctrl_break is not None:
                try:
                    process.send_signal(ctrl_break)
                    process.wait(timeout=grace_sec)
                    return
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    pass
            try:
                subprocess.call(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                process.wait(timeout=grace_sec)
                return
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
            process.kill()
            return
        process.kill()

    def run_subprocess(
        self,
        command: Any,
        cwd: str,
        timeout_sec: int,
        shell: bool,
        stop_event: Optional[threading.Event] = None,
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
            creationflags=(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0),
        )
        timed_out = False
        interrupted = False
        deadline = started + timeout_sec
        stdout = ""
        stderr = ""
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                timed_out = True
                self.terminate_process_tree(process)
                stdout, stderr = process.communicate()
                break
            try:
                stdout, stderr = process.communicate(timeout=min(0.2, remaining))
                break
            except subprocess.TimeoutExpired:
                if stop_event is not None and stop_event.is_set():
                    interrupted = True
                    self.terminate_process_tree(process)
                    stdout, stderr = process.communicate()
                    break
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
            "interrupted": interrupted,
        }

    def build_command_observation(
        self,
        tool_name: str,
        command_text: str,
        cwd: str,
        result: Dict[str, Any],
    ) -> Observation:
        success = (result["exit_code"] == 0) and (not result["timed_out"])
        success = success and (not result.get("interrupted"))
        error = None
        if result.get("interrupted"):
            error = "命令执行被中断，已强制终止。"
        elif result["timed_out"]:
            error = "命令执行超时，已强制终止。"
        elif result["exit_code"] != 0:
            error = "命令退出码为 %s。" % result["exit_code"]
        runtime = self.runtime_environment_snapshot()
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
            "interrupted": bool(result.get("interrupted")),
            "toolchain_root": runtime.get("resolved_tool_roots", {}).get("llvm_root") or None,
            "runtime_source": runtime.get("runtime_source") or "",
            "bundled_tools_ready": bool(runtime.get("bundled_tools_ready")),
            "fallback_warnings": list(runtime.get("fallback_warnings") or []),
            "resolved_tool_roots": dict(runtime.get("resolved_tool_roots") or {}),
        }
        if result.get("interrupted"):
            data.update(
                {
                    "error_kind": "interrupted",
                    "retryable": False,
                    "blocked_by": "user_cancelled",
                    "suggested_next_step": "用户取消了当前会话；如需继续，请恢复会话或重新提交请求。",
                }
            )
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
        resolved_command, managed_tool, _ = self.rewrite_command_for_managed_tools(command_text)
        result = self.run_subprocess(
            command=resolved_command,
            cwd=cwd,
            timeout_sec=timeout_sec,
            shell=True,
            stop_event=self.get_interrupt_event(),
        )
        if diagnostic:
            observation = self.build_diagnostic_observation(tool_name, resolved_command, cwd, result)
        else:
            observation = self.build_command_observation(tool_name, resolved_command, cwd, result)
        if isinstance(observation.data, dict):
            data = dict(observation.data)
            data["requested_command"] = command_text
            if managed_tool:
                data["managed_primary_tool"] = managed_tool
            observation.data = data
        return observation

    # ----------------------------------------------------------- git helpers

    def git_relative_arg(self, path: str) -> Optional[str]:
        resolved = self.resolve_path(path)
        relative = self.relative_path(resolved)
        if relative == ".":
            return None
        return relative

    def run_git_command(self, args: List[str]) -> Dict[str, Any]:
        if args:
            executable, _ = self.resolve_managed_command_executable(args[0])
            args = [executable] + list(args[1:])
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
