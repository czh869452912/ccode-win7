from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

STATUS_TIMEOUT_SEC = 5
DIFF_TIMEOUT_SEC = 10
MAX_STATUS_OUTPUT_BYTES = 512 * 1024
MAX_DIFF_OUTPUT_BYTES = 1024 * 1024
ALLOWED_DIFF_SCOPES = ("unstaged", "staged")


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _truthy_env(value: str) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _truncate_text(value: str, max_bytes: int) -> Tuple[str, bool]:
    raw = str(value or "")
    encoded = raw.encode("utf-8", "replace")
    if len(encoded) <= max_bytes:
        return raw, False
    truncated = encoded[: max(0, max_bytes)].decode("utf-8", "replace")
    return truncated, True


def default_command_runner(
    command: List[str],
    cwd: str,
    timeout_sec: int,
    max_output_bytes: int,
    env: Dict[str, str],
) -> Dict[str, Any]:
    started = time.time()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        shell=False,
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
        process.kill()
        stdout, stderr = process.communicate()
    stdout, stdout_truncated = _truncate_text(stdout or "", max_output_bytes)
    stderr, stderr_truncated = _truncate_text(stderr or "", max_output_bytes)
    return {
        "exit_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "truncated": bool(stdout_truncated or stderr_truncated),
        "duration_ms": int((time.time() - started) * 1000),
    }


def _empty_counts() -> Dict[str, int]:
    return {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0, "total": 0}


def _provider_from_remote_url(remote_url: str) -> Optional[Dict[str, str]]:
    text = str(remote_url or "").strip()
    if not text:
        return None
    host = ""
    scp_style = re.match(r"^[^@]+@([^:/\s]+)[:/]", text)
    if scp_style:
        host = scp_style.group(1).lower()
    else:
        url_style = re.match(r"^[a-z][a-z0-9+.-]*://([^/\s]+)", text, re.IGNORECASE)
        if url_style:
            host = url_style.group(1).lower()
    if not host:
        return None
    if "github" in host:
        kind = "github"
        name = "GitHub" if host == "github.com" else "GitHub Self-Hosted"
    elif "gitlab" in host:
        kind = "gitlab"
        name = "GitLab" if host == "gitlab.com" else "GitLab Self-Hosted"
    elif host == "dev.azure.com" or host.endswith(".visualstudio.com"):
        kind = "azure-devops"
        name = "Azure DevOps"
    elif "bitbucket" in host:
        kind = "bitbucket"
        name = "Bitbucket" if host == "bitbucket.org" else "Bitbucket Self-Hosted"
    else:
        kind = "unknown"
        name = host
    return {"kind": kind, "name": name, "base_url": "https://%s" % host}


class SourceControlService(object):
    def __init__(
        self,
        workspace_root: str,
        git_executable: Optional[str] = None,
        command_runner: Optional[
            Callable[[List[str], str, int, int, Dict[str, str]], Dict[str, Any]]
        ] = None,
        env_builder: Optional[Callable[[], Dict[str, str]]] = None,
        runtime_source: str = "",
    ) -> None:
        self.workspace_root = os.path.realpath(workspace_root)
        self.command_runner = command_runner or default_command_runner
        self.env_builder = env_builder
        self.runtime_source = str(runtime_source or "")
        self.git_executable = (
            git_executable if git_executable is not None else self._resolve_git_executable()
        )

    def status(self) -> Dict[str, Any]:
        base = self._base_status()
        if not self.git_executable:
            return base

        status_result = self._run_git(
            ["status", "--short", "--branch"],
            timeout_sec=STATUS_TIMEOUT_SEC,
            max_output_bytes=MAX_STATUS_OUTPUT_BYTES,
        )
        if self._is_not_repo(status_result):
            base.update({"git_available": True, "diagnostics": self._diagnostics(["not_a_repo"])})
            return base
        if not self._command_ok(status_result):
            base.update(
                {
                    "git_available": True,
                    "diagnostics": self._diagnostics(["git_failed"], status_result),
                }
            )
            return base

        lines = [line for line in str(status_result.get("stdout") or "").splitlines() if line]
        branch, files = self._parse_status_lines(lines)
        head = self._first_stdout_line(
            self._run_git(
                ["rev-parse", "--short", "HEAD"], STATUS_TIMEOUT_SEC, MAX_STATUS_OUTPUT_BYTES
            )
        )
        remote_url = self._first_stdout_line(
            self._run_git(
                ["remote", "get-url", "origin"], STATUS_TIMEOUT_SEC, MAX_STATUS_OUTPUT_BYTES
            )
        )
        stats = self._collect_numstat()
        files = [self._with_stats(item, stats) for item in files]
        counts = self._counts(files)
        base.update(
            {
                "git_available": True,
                "is_repo": True,
                "branch": branch,
                "head": head,
                "has_primary_remote": bool(remote_url),
                "provider": _provider_from_remote_url(remote_url),
                "is_dirty": counts["total"] > 0,
                "counts": counts,
                "files": files,
                "diagnostics": self._diagnostics(
                    ["status_truncated"] if status_result.get("truncated") else []
                ),
            }
        )
        return base

    def diff(self, path: str, scope: str = "unstaged") -> Dict[str, Any]:
        normalized_scope = str(scope or "unstaged")
        if normalized_scope not in ALLOWED_DIFF_SCOPES:
            raise ValueError("invalid_diff_scope")
        relative_path = self._relative_workspace_path(path)
        if not self.git_executable:
            return self._unavailable_diff(relative_path, normalized_scope, "git_unavailable")
        args = ["diff"]
        if normalized_scope == "staged":
            args.append("--cached")
        args.extend(["--", relative_path])
        result = self._run_git(args, DIFF_TIMEOUT_SEC, MAX_DIFF_OUTPUT_BYTES)
        if self._is_not_repo(result):
            return self._unavailable_diff(relative_path, normalized_scope, "not_a_repo")
        if not self._command_ok(result):
            return self._unavailable_diff(relative_path, normalized_scope, "git_failed", result)
        diff_text = str(result.get("stdout") or "")
        return {
            "workspace_root": self.workspace_root,
            "path": relative_path,
            "scope": normalized_scope,
            "available": bool(diff_text),
            "binary": self._is_binary_diff(diff_text),
            "diff": diff_text,
            "file_count": diff_text.count("diff --git "),
            "line_count": len(diff_text.splitlines()),
            "truncated": bool(result.get("truncated")),
            "reason": "path_not_changed" if not diff_text else "",
            "updated_at": _utc_now(),
        }

    def discover(self) -> Dict[str, Any]:
        return {
            "git_available": bool(self.git_executable),
            "git_executable": self.git_executable or "",
            "runtime_source": self.runtime_source,
        }

    def _base_status(self) -> Dict[str, Any]:
        return {
            "workspace_root": self.workspace_root,
            "is_repo": False,
            "git_available": bool(self.git_executable),
            "git_executable": self.git_executable or "",
            "runtime_source": self.runtime_source,
            "branch": "",
            "head": "",
            "has_primary_remote": False,
            "provider": None,
            "is_dirty": False,
            "counts": _empty_counts(),
            "files": [],
            "updated_at": _utc_now(),
            "diagnostics": self._diagnostics(),
        }

    def _resolve_git_executable(self) -> str:
        candidates = []
        bundle_root = os.environ.get("EMBEDAGENT_BUNDLE_ROOT", "").strip()
        if bundle_root:
            candidates.extend(
                [
                    os.path.join(bundle_root, "bin", "git", "cmd", "git.exe"),
                    os.path.join(bundle_root, "bin", "git", "bin", "git.exe"),
                ]
            )
        candidates.extend(
            [
                os.path.join(self.workspace_root, "bin", "git", "cmd", "git.exe"),
                os.path.join(self.workspace_root, "bin", "git", "bin", "git.exe"),
            ]
        )
        for candidate in candidates:
            if os.path.isfile(candidate):
                if "bin%s git" % os.sep in candidate:
                    self.runtime_source = self.runtime_source or "bundle"
                return os.path.realpath(candidate)
        if _truthy_env(os.environ.get("EMBEDAGENT_ALLOW_SYSTEM_TOOL_FALLBACK", "")):
            self.runtime_source = self.runtime_source or "system"
            return "git"
        return ""

    def _build_env(self) -> Dict[str, str]:
        if self.env_builder is not None:
            return dict(self.env_builder())
        env = os.environ.copy()
        executable = self.git_executable or ""
        if executable and executable not in ("git", "git.exe"):
            git_dir = os.path.dirname(executable)
            sibling_bin = os.path.join(os.path.dirname(git_dir), "bin")
            entries = [item for item in (git_dir, sibling_bin) if os.path.isdir(item)]
            if entries:
                current_path = env.get("PATH", "")
                env["PATH"] = os.pathsep.join(entries + ([current_path] if current_path else []))
        return env

    def _run_git(
        self,
        args: List[str],
        timeout_sec: int,
        max_output_bytes: int,
    ) -> Dict[str, Any]:
        command = [self.git_executable, "-C", self.workspace_root] + list(args)
        return self.command_runner(
            command, self.workspace_root, timeout_sec, max_output_bytes, self._build_env()
        )

    def _relative_workspace_path(self, path: str) -> str:
        text = str(path or "").strip()
        if not text:
            raise ValueError("path_outside_workspace")
        candidate = text if os.path.isabs(text) else os.path.join(self.workspace_root, text)
        resolved = os.path.realpath(candidate)
        workspace_norm = os.path.normcase(self.workspace_root)
        resolved_norm = os.path.normcase(resolved)
        if not (
            resolved_norm == workspace_norm or resolved_norm.startswith(workspace_norm + os.sep)
        ):
            raise ValueError("path_outside_workspace")
        relative = os.path.relpath(resolved, self.workspace_root)
        return "." if relative == "." else relative.replace(os.sep, "/")

    def _parse_status_lines(self, lines: List[str]) -> Tuple[str, List[Dict[str, Any]]]:
        branch = ""
        files = []
        for line in lines:
            if line.startswith("## "):
                branch = self._parse_branch(line[3:])
                continue
            if len(line) < 3:
                continue
            index_status = line[0]
            worktree_status = line[1]
            file_path = line[3:].strip()
            if " -> " in file_path:
                file_path = file_path.split(" -> ", 1)[1].strip()
            group = self._group_for_status(index_status, worktree_status)
            files.append(
                {
                    "path": file_path,
                    "display_path": file_path,
                    "status": self._status_label(index_status, worktree_status),
                    "index_status": index_status.strip(),
                    "worktree_status": worktree_status.strip(),
                    "group": group,
                    "insertions": 0,
                    "deletions": 0,
                    "binary": False,
                    "diff_scopes": self._diff_scopes(group, index_status, worktree_status),
                }
            )
        return branch, files

    def _parse_branch(self, branch_line: str) -> str:
        value = str(branch_line or "").strip()
        if "..." in value:
            return value.split("...", 1)[0].strip()
        if value.startswith("No commits yet on "):
            return value[len("No commits yet on ") :].strip()
        return value

    def _group_for_status(self, index_status: str, worktree_status: str) -> str:
        pair = "%s%s" % (index_status, worktree_status)
        if pair in ("UU", "AA", "DD", "AU", "UA", "DU", "UD"):
            return "conflicted"
        if pair == "??":
            return "untracked"
        if index_status.strip():
            return "staged"
        return "unstaged"

    def _status_label(self, index_status: str, worktree_status: str) -> str:
        pair = "%s%s" % (index_status, worktree_status)
        if pair in ("UU", "AA", "DD", "AU", "UA", "DU", "UD"):
            return "conflicted"
        if pair == "??":
            return "untracked"
        code = (worktree_status.strip() or index_status.strip() or "M").upper()
        return {
            "A": "added",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "U": "conflicted",
            "M": "modified",
        }.get(code, "modified")

    def _diff_scopes(self, group: str, index_status: str, worktree_status: str) -> List[str]:
        scopes = []
        if group == "staged" or index_status.strip():
            scopes.append("staged")
        if group == "unstaged" or worktree_status.strip():
            scopes.append("unstaged")
        return scopes

    def _collect_numstat(self) -> Dict[str, Dict[str, Any]]:
        stats = {}
        for scope, args in (
            ("unstaged", ["diff", "--numstat"]),
            ("staged", ["diff", "--cached", "--numstat"]),
        ):
            result = self._run_git(args, STATUS_TIMEOUT_SEC, MAX_STATUS_OUTPUT_BYTES)
            if not self._command_ok(result):
                continue
            for line in str(result.get("stdout") or "").splitlines():
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                insertions, deletions, file_path = parts[0], parts[1], parts[2]
                stats.setdefault(file_path, {})[scope] = {
                    "insertions": 0 if insertions == "-" else int(insertions or 0),
                    "deletions": 0 if deletions == "-" else int(deletions or 0),
                    "binary": insertions == "-" or deletions == "-",
                }
        return stats

    def _with_stats(self, item: Dict[str, Any], stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        path_stats = stats.get(item["path"]) or {}
        selected = {}
        for scope in item.get("diff_scopes") or []:
            if scope in path_stats:
                selected = path_stats[scope]
                break
        result = dict(item)
        result["insertions"] = int(selected.get("insertions") or 0)
        result["deletions"] = int(selected.get("deletions") or 0)
        result["binary"] = bool(selected.get("binary"))
        return result

    def _counts(self, files: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = _empty_counts()
        for item in files:
            group = item.get("group")
            if group in counts:
                counts[group] += 1
            counts["total"] += 1
        return counts

    def _diagnostics(
        self,
        warnings: Optional[List[str]] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "status_truncated": False,
            "stats_truncated": False,
            "warnings": list(warnings or []),
        }
        if result:
            payload["status_truncated"] = bool(result.get("truncated"))
            if result.get("timed_out"):
                payload["warnings"].append("git_timeout")
        return payload

    def _unavailable_diff(
        self,
        path: str,
        scope: str,
        reason: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "workspace_root": self.workspace_root,
            "path": path,
            "scope": scope,
            "available": False,
            "binary": False,
            "diff": "",
            "file_count": 0,
            "line_count": 0,
            "truncated": bool((result or {}).get("truncated")),
            "reason": reason,
            "updated_at": _utc_now(),
        }

    def _first_stdout_line(self, result: Dict[str, Any]) -> str:
        if not self._command_ok(result):
            return ""
        for line in str(result.get("stdout") or "").splitlines():
            value = line.strip()
            if value:
                return value
        return ""

    def _command_ok(self, result: Dict[str, Any]) -> bool:
        return int(result.get("exit_code") or 0) == 0 and not bool(result.get("timed_out"))

    def _is_not_repo(self, result: Dict[str, Any]) -> bool:
        combined = ("%s\n%s" % (result.get("stdout") or "", result.get("stderr") or "")).lower()
        return "not a git repository" in combined

    def _is_binary_diff(self, diff_text: str) -> bool:
        lowered = str(diff_text or "").lower()
        return "binary files " in lowered or "git binary patch" in lowered
