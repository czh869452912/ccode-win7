from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from embedagent.project_memory import ProjectMemoryStore
from embedagent.session import Observation, Session


@dataclass
class IntelligenceEvidence:
    provider: str
    title: str
    content: str
    priority: int = 50
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkspaceIntelligenceProvider(object):
    name = "provider"

    def collect(
        self,
        session: Session,
        mode_name: str,
        tools: Any,
        project_memory: Optional[ProjectMemoryStore] = None,
    ) -> List[IntelligenceEvidence]:
        return []


class WorkingSetProvider(WorkspaceIntelligenceProvider):
    name = "working_set"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        modified = []
        seen = set()
        for turn in reversed(session.turns):
            for observation in reversed(turn.observations):
                if observation.tool_name not in ("write_file", "edit_file"):
                    continue
                if not isinstance(observation.data, dict):
                    continue
                path = str(observation.data.get("path") or "")
                if not path or path in seen:
                    continue
                seen.add(path)
                modified.append(path)
                if len(modified) >= 6:
                    break
            if len(modified) >= 6:
                break
        if not modified:
            return []
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Recent Modified Files",
                content="最近修改文件：%s" % ", ".join(modified),
                priority=95,
                tags=["working_set", mode_name],
                metadata={"paths": modified},
            )
        ]


class ProjectMemoryProvider(WorkspaceIntelligenceProvider):
    name = "project_memory"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        if project_memory is None:
            return []
        content = project_memory.build_system_message(mode_name, 1200)
        if not content:
            return []
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Project Memory",
                content=content,
                priority=90,
                tags=["project_memory", mode_name],
            )
        ]


class RecipeProvider(WorkspaceIntelligenceProvider):
    name = "recipes"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        if not hasattr(tools, "workspace_recipes"):
            return []
        payload = tools.workspace_recipes() or {}
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list) or not items:
            return []
        ranked = self._rank_items(mode_name, items)
        selected = []
        selected_ids = []
        selected_sources = []
        for item in ranked[:4]:
            if not isinstance(item, dict):
                continue
            selected_ids.append(str(item.get("id") or ""))
            selected_sources.append(str(item.get("source") or ""))
            selected.append(
                "[%s] %s" % (
                    str(item.get("tool_name") or ""),
                    str(item.get("id") or item.get("label") or ""),
                )
            )
        if not selected:
            return []
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Active Recipes",
                content="工作区 recipe：%s" % "; ".join(selected),
                priority=85 if mode_name in ("code", "verify", "debug") else 55,
                tags=["recipe", mode_name],
                metadata={"count": len(items), "selected_ids": selected_ids, "selected_sources": selected_sources},
            )
        ]

    def _rank_items(self, mode_name: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        preferred = {
            "verify": {"run_tests": 0, "run_clang_tidy": 1, "run_clang_analyzer": 2, "collect_coverage": 3, "compile_project": 4},
            "code": {"compile_project": 0, "run_tests": 1, "run_clang_tidy": 2},
            "debug": {"run_tests": 0, "compile_project": 1, "run_clang_tidy": 2, "run_clang_analyzer": 3},
            "explore": {"compile_project": 0, "run_tests": 1},
            "spec": {"compile_project": 0, "run_tests": 1},
        }.get(mode_name, {})
        source_rank = {
            "code": {"project": 0, "detected": 1, "history": 2},
            "debug": {"project": 0, "detected": 1, "history": 2},
            "verify": {"project": 0, "history": 1, "detected": 2},
            "explore": {"project": 0, "detected": 1, "history": 2},
            "spec": {"project": 0, "detected": 1, "history": 2},
        }.get(mode_name, {})
        return sorted(
            items,
            key=lambda item: (
                preferred.get(str(item.get("tool_name") or ""), 99),
                source_rank.get(str(item.get("source") or ""), 99),
                self._stage_rank(mode_name, item),
                str(item.get("id") or ""),
            ),
        )

    def _stage_rank(self, mode_name: str, item: Dict[str, Any]) -> int:
        stage = str(item.get("stage") or "")
        if not stage:
            return 0
        if mode_name in ("code", "debug"):
            order = {"build": 0, "test": 1, "configure": 2}
        elif mode_name == "verify":
            order = {"test": 0, "build": 1, "configure": 2}
        else:
            order = {"build": 0, "test": 1, "configure": 2}
        return int(order.get(stage, 99))


class CtagsProvider(WorkspaceIntelligenceProvider):
    name = "ctags"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        runtime = tools.runtime_environment_snapshot() if hasattr(tools, "runtime_environment_snapshot") else {}
        roots = runtime.get("resolved_tool_roots") if isinstance(runtime, dict) else {}
        ctags_path = str((roots or {}).get("ctags_exe") or "")
        tags_file = os.path.join(tools.workspace, "tags")
        if os.path.isfile(tags_file):
            entries = _load_ctags_entries(tags_file, limit=16)
            focus_paths = _focus_paths_from_session(session)
            if focus_paths:
                entries.sort(key=lambda item: (0 if item["path"] in focus_paths else 1, item["path"], item["name"]))
            entries = entries[:5]
            if entries:
                rendered = []
                for item in entries:
                    rendered.append("%s -> %s (%s)" % (item["name"], item["path"], item["kind"]))
                content = "关键符号：%s" % "; ".join(rendered)
            else:
                content = "检测到 tags 文件：%s" % os.path.relpath(tags_file, tools.workspace).replace(os.sep, "/")
        elif ctags_path:
            content = "ctags 可用：%s；当前还没有预生成 tags 文件。" % ctags_path
        else:
            content = "ctags 尚未就绪；符号情报会退化到 grep/诊断。"
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Symbol Intelligence",
                content=content,
                priority=80 if mode_name in ("code", "debug") else 40,
                tags=["symbol", mode_name],
                metadata={"ctags_available": bool(ctags_path), "tags_file": os.path.isfile(tags_file), "parsed_tags": bool(os.path.isfile(tags_file) and _load_ctags_entries(tags_file, limit=1)), "focus_paths": focus_paths if os.path.isfile(tags_file) else []},
            )
        ]


class DiagnosticsProvider(WorkspaceIntelligenceProvider):
    name = "diagnostics"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        evidence = []
        working_paths = set(_working_set_paths_from_session(session))
        focus_paths = set(_focus_paths_from_session(session))
        observations = list(reversed(_all_observations(session)))
        pathless_summary = _group_pathless_diagnostic_summary(observations)
        if pathless_summary is not None and mode_name == "verify":
            evidence.append(
                IntelligenceEvidence(
                    provider=self.name,
                    title=str(pathless_summary["title"]),
                    content=str(pathless_summary["content"]),
                    priority=105,
                    tags=["diagnostic", mode_name] + list(pathless_summary["tool_names"]),
                    metadata={
                        "tool_name": pathless_summary["tool_names"][0] if pathless_summary["tool_names"] else "",
                        "tool_names": list(pathless_summary["tool_names"]),
                        "focus_match": False,
                        "path": "",
                        "diagnostic_count": int(pathless_summary["diagnostic_count"] or 0),
                        "group_kind": str(pathless_summary["group_kind"]),
                    },
                )
            )
        hotspots = _group_diagnostic_hotspots(observations, working_paths, focus_paths)
        for hotspot in hotspots[:2]:
            tool_names = hotspot["tool_names"]
            evidence.append(
                IntelligenceEvidence(
                    provider=self.name,
                    title="Diagnostic Hotspot",
                    content="诊断热点 %s：%s 条诊断，来自 %s。最新：%s" % (
                        hotspot["path"],
                        hotspot["diagnostic_count"],
                        ", ".join(tool_names),
                        hotspot["latest_detail"],
                    ),
                    priority=100 if mode_name in ("code", "debug", "verify") else 60,
                    tags=["diagnostic", mode_name] + list(tool_names),
                    metadata={
                        "tool_name": tool_names[0] if tool_names else "",
                        "tool_names": list(tool_names),
                        "focus_match": bool(hotspot["focus_match"]),
                        "path": hotspot["path"],
                        "diagnostic_count": hotspot["diagnostic_count"],
                        "group_kind": "path_hotspot",
                    },
                )
            )
        if len(evidence) >= 2:
            return evidence
        if pathless_summary is not None and not any(item.metadata.get("group_kind") == str(pathless_summary["group_kind"]) for item in evidence):
            evidence.append(
                IntelligenceEvidence(
                    provider=self.name,
                    title=str(pathless_summary["title"]),
                    content=str(pathless_summary["content"]),
                    priority=95 if mode_name in ("code", "debug", "verify") else 55,
                    tags=["diagnostic", mode_name] + list(pathless_summary["tool_names"]),
                    metadata={
                        "tool_name": pathless_summary["tool_names"][0] if pathless_summary["tool_names"] else "",
                        "tool_names": list(pathless_summary["tool_names"]),
                        "focus_match": False,
                        "path": "",
                        "diagnostic_count": int(pathless_summary["diagnostic_count"] or 0),
                        "group_kind": str(pathless_summary["group_kind"]),
                    },
                )
            )
            if len(evidence) >= 2:
                return evidence
        seen_keys = set()
        observations.sort(
            key=lambda observation: (
                0 if _observation_primary_path(observation) in working_paths else 1,
                0 if _observation_primary_path(observation) in focus_paths else 1,
                0 if observation.tool_name in ("run_tests", "compile_project", "run_clang_tidy", "run_clang_analyzer") else 1,
            )
        )
        for observation in observations:
            if observation.tool_name not in (
                "compile_project",
                "run_tests",
                "run_clang_tidy",
                "run_clang_analyzer",
                "collect_coverage",
                "report_quality",
            ):
                continue
            if not isinstance(observation.data, dict):
                continue
            detail = _diagnostic_detail(observation)
            if not detail:
                continue
            primary_path = _observation_primary_path(observation)
            key = "%s|%s|%s" % (observation.tool_name, primary_path, detail)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if primary_path and any(item.metadata.get("path") == primary_path for item in evidence):
                continue
            focus_match = primary_path in working_paths or primary_path in focus_paths
            tags = ["diagnostic", observation.tool_name, mode_name]
            metadata = {"tool_name": observation.tool_name, "focus_match": focus_match, "path": primary_path, "group_kind": "single_observation"}
            evidence.append(
                IntelligenceEvidence(
                    provider=self.name,
                    title="Recent Diagnostics",
                    content=detail,
                    priority=100 if mode_name in ("code", "debug", "verify") else 60,
                    tags=tags,
                    metadata=metadata,
                )
            )
            if len(evidence) >= 2:
                break
        return evidence


class GitStateProvider(WorkspaceIntelligenceProvider):
    name = "git"

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        if mode_name not in ("explore", "spec", "code", "debug"):
            return []
        observation = tools.execute("git_status", {"path": "."})
        if not isinstance(observation.data, dict):
            return []
        branch = str(observation.data.get("branch") or "")
        entries = observation.data.get("entries") if isinstance(observation.data.get("entries"), list) else []
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="Git Workspace State",
                content="Git 分支 `%s`，脏文件 %s 个。" % (branch or "-", len(entries)),
                priority=50,
                tags=["git", mode_name],
                metadata={"branch": branch, "dirty_count": len(entries)},
            )
        ]


class LlspBackend(object):
    def collect(self, workspace: str, session: Session, mode_name: str) -> List[Dict[str, Any]]:
        return []


class LlspProvider(WorkspaceIntelligenceProvider):
    name = "llsp"

    def __init__(self, backend: Optional[LlspBackend] = None) -> None:
        self.backend = backend

    def collect(self, session: Session, mode_name: str, tools: Any, project_memory: Optional[ProjectMemoryStore] = None) -> List[IntelligenceEvidence]:
        if self.backend is not None:
            items = self.backend.collect(tools.workspace, session, mode_name) or []
            evidence = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                evidence.append(
                    IntelligenceEvidence(
                        provider=self.name,
                        title=str(item.get("title") or "LLSP Evidence"),
                        content=str(item.get("content") or ""),
                        priority=int(item.get("priority") or 75),
                        tags=["llsp", mode_name],
                        metadata=dict(item.get("metadata") or {}),
                    )
                )
            if evidence:
                return evidence
        return [
            IntelligenceEvidence(
                provider=self.name,
                title="LLSP Provider",
                content="LLSP provider 已预留接口，当前使用空实现并自动退化到 ctags + grep + diagnostics。",
                priority=30,
                tags=["llsp", "contract"],
                metadata={"available": False},
            )
        ]


class WorkspaceIntelligenceBroker(object):
    def __init__(self, providers: Optional[List[WorkspaceIntelligenceProvider]] = None) -> None:
        self.providers = providers or [
            WorkingSetProvider(),
            ProjectMemoryProvider(),
            RecipeProvider(),
            CtagsProvider(),
            DiagnosticsProvider(),
            GitStateProvider(),
            LlspProvider(),
        ]

    def collect(
        self,
        session: Session,
        mode_name: str,
        tools: Any,
        project_memory: Optional[ProjectMemoryStore] = None,
    ) -> List[IntelligenceEvidence]:
        collected = []
        for provider in self.providers:
            collected.extend(provider.collect(session, mode_name, tools, project_memory))
        collected = self._filter_for_mode(mode_name, collected)
        collected.sort(key=lambda item: (-int(item.priority or 0), item.provider, item.title))
        return collected

    def render_system_message(
        self,
        session: Session,
        mode_name: str,
        tools: Any,
        project_memory: Optional[ProjectMemoryStore] = None,
        limit: int = 3,
        char_limit: int = 1600,
    ) -> str:
        evidence = self.collect(session, mode_name, tools, project_memory)[:limit]
        if not evidence:
            return ""
        lines = ["以下是当前工作区的工程情报，仅供当前任务参考："]
        for item in evidence:
            lines.append("- %s: %s" % (item.title, item.content))
        message = "\n".join(lines)
        return message[:char_limit]

    def _filter_for_mode(self, mode_name: str, evidence: List[IntelligenceEvidence]) -> List[IntelligenceEvidence]:
        allowed_tags = {
            "explore": {"project_memory", "git", "recipe", "llsp", "symbol"},
            "spec": {"project_memory", "git", "recipe", "llsp", "symbol"},
            "code": {"working_set", "project_memory", "recipe", "symbol", "diagnostic", "llsp"},
            "debug": {"working_set", "project_memory", "recipe", "symbol", "diagnostic", "git", "llsp"},
            "verify": {"project_memory", "recipe", "diagnostic", "llsp"},
        }.get(mode_name)
        if not allowed_tags:
            return evidence
        filtered = []
        for item in evidence:
            if not item.tags:
                filtered.append(item)
                continue
            if any(tag in allowed_tags for tag in item.tags):
                filtered.append(item)
        return filtered


def _all_observations(session: Session) -> List[Observation]:
    observations = []
    for turn in session.turns:
        observations.extend(turn.observations)
    return observations


def _diagnostic_detail(observation: Observation) -> str:
    if not isinstance(observation.data, dict):
        return ""
    data = observation.data
    if observation.tool_name == "run_tests":
        summary = data.get("test_summary") if isinstance(data.get("test_summary"), dict) else {}
        total = int(summary.get("total") or 0)
        failed = int(summary.get("failed") or 0)
        return "最近测试：total=%s, failed=%s。" % (total, failed)
    if observation.tool_name == "collect_coverage":
        summary = data.get("coverage_summary") if isinstance(data.get("coverage_summary"), dict) else {}
        line_cov = summary.get("line_coverage")
        if line_cov is not None:
            return "最近覆盖率：line coverage %.2f%%。" % float(line_cov)
        return ""
    diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
    if diagnostics:
        first = diagnostics[0] if isinstance(diagnostics[0], dict) else {}
        return "%s:%s:%s %s" % (
            first.get("file") or "?",
            first.get("line") or 1,
            first.get("column") or 1,
            first.get("message") or observation.error or "",
        )
    if observation.error:
        return "%s: %s" % (observation.tool_name, observation.error)
    return ""


def _observation_primary_path(observation: Observation) -> str:
    if not isinstance(observation.data, dict):
        return ""
    direct = observation.data.get("path")
    if isinstance(direct, str) and direct:
        return direct.replace("\\", "/")
    diagnostics = observation.data.get("diagnostics") if isinstance(observation.data.get("diagnostics"), list) else []
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        path = item.get("file") or item.get("path")
        if isinstance(path, str) and path:
            return path.replace("\\", "/")
    return ""


def _load_ctags_entries(path: str, limit: int = 5) -> List[Dict[str, str]]:
    entries = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("!_TAG_"):
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                name = parts[0].strip()
                file_path = parts[1].strip().replace("\\", "/")
                rest = parts[3:]
                kind = ""
                for token in rest:
                    token = token.strip()
                    if token.startswith("kind:"):
                        kind = token.split(":", 1)[1].strip()
                        break
                    if len(token) == 1:
                        kind = token
                        break
                entries.append(
                    {
                        "name": name,
                        "path": file_path,
                        "kind": kind or "?",
                    }
                )
                if len(entries) >= limit:
                    break
    except OSError:
        return []
    return entries


def _focus_paths_from_session(session: Session) -> List[str]:
    seen = set()
    paths = []
    for observation in reversed(_all_observations(session)):
        if not isinstance(observation.data, dict):
            continue
        direct = observation.data.get("path")
        if isinstance(direct, str) and direct and direct not in seen:
            seen.add(direct)
            paths.append(direct.replace("\\", "/"))
        diagnostics = observation.data.get("diagnostics") if isinstance(observation.data.get("diagnostics"), list) else []
        for item in diagnostics:
            if not isinstance(item, dict):
                continue
            path = item.get("file") or item.get("path")
            if isinstance(path, str) and path and path not in seen:
                seen.add(path)
                paths.append(path.replace("\\", "/"))
    return paths[:8]


def _working_set_paths_from_session(session: Session) -> List[str]:
    seen = set()
    paths = []
    for observation in reversed(_all_observations(session)):
        if observation.tool_name not in ("read_file", "write_file", "edit_file"):
            continue
        if not isinstance(observation.data, dict):
            continue
        path = observation.data.get("path")
        if not isinstance(path, str) or not path:
            continue
        normalized = path.replace("\\", "/")
        if normalized in seen:
            continue
        seen.add(normalized)
        paths.append(normalized)
    return paths[:8]


def _group_diagnostic_hotspots(
    observations: List[Observation],
    working_paths: set,
    focus_paths: set,
) -> List[Dict[str, Any]]:
    groups = {}
    order = 0
    for observation in observations:
        if observation.tool_name not in (
            "compile_project",
            "run_tests",
            "run_clang_tidy",
            "run_clang_analyzer",
            "collect_coverage",
            "report_quality",
        ):
            continue
        if not isinstance(observation.data, dict):
            continue
        primary_path = _observation_primary_path(observation)
        if not primary_path:
            continue
        detail = _diagnostic_detail(observation)
        if not detail:
            continue
        group = groups.get(primary_path)
        if group is None:
            group = {
                "path": primary_path,
                "details": [],
                "tool_names": [],
                "diagnostic_count": 0,
                "working_match": primary_path in working_paths,
                "focus_match": primary_path in focus_paths,
                "first_seen_order": order,
                "latest_detail": detail,
            }
            groups[primary_path] = group
            order += 1
        group["details"].append(detail)
        if observation.tool_name not in group["tool_names"]:
            group["tool_names"].append(observation.tool_name)
        group["diagnostic_count"] += _observation_diagnostic_count(observation)
        if len(group["details"]) == 1:
            group["latest_detail"] = detail
    ranked = list(groups.values())
    ranked.sort(
        key=lambda item: (
            0 if item["working_match"] else 1,
            0 if item["focus_match"] else 1,
            -int(item["diagnostic_count"] or 0),
            int(item["first_seen_order"] or 0),
            str(item["path"] or ""),
        )
    )
    return ranked


def _group_pathless_diagnostic_summary(observations: List[Observation]) -> Optional[Dict[str, Any]]:
    tool_names = []
    tool_name_set = set()
    reasons = []
    diagnostic_count = 0
    latest_detail = ""
    has_quality_gate = False
    for observation in observations:
        if observation.tool_name not in (
            "compile_project",
            "run_tests",
            "run_clang_tidy",
            "run_clang_analyzer",
            "collect_coverage",
            "report_quality",
        ):
            continue
        if not isinstance(observation.data, dict):
            continue
        if _observation_primary_path(observation):
            continue
        detail = _diagnostic_detail(observation)
        if not detail and observation.tool_name != "report_quality":
            continue
        if observation.tool_name not in tool_name_set:
            tool_name_set.add(observation.tool_name)
            tool_names.append(observation.tool_name)
        diagnostic_count += _observation_diagnostic_count(observation)
        if not latest_detail and detail:
            latest_detail = detail
        if observation.tool_name == "report_quality" and not observation.success:
            has_quality_gate = True
            for item in observation.data.get("reasons") or []:
                text = str(item or "").strip()
                if text and text not in reasons:
                    reasons.append(text)
    if not tool_names:
        return None
    if has_quality_gate:
        content_parts = ["质量门未通过"]
        if reasons:
            content_parts.append("；".join(reasons))
        content_parts.append("相关检查：%s" % ", ".join(tool_names))
        return {
            "title": "Quality Gate Summary",
            "content": "。".join([part for part in content_parts if part]) + "。",
            "tool_names": tool_names,
            "diagnostic_count": diagnostic_count or len(reasons) or len(tool_names),
            "group_kind": "quality_gate_summary",
        }
    if len(tool_names) < 2:
        return None
    content = "无路径诊断摘要：来自 %s。最新：%s" % (
        ", ".join(tool_names),
        latest_detail or "最近一次检查未通过。",
    )
    return {
        "title": "Pathless Diagnostics",
        "content": content,
        "tool_names": tool_names,
        "diagnostic_count": diagnostic_count or len(tool_names),
        "group_kind": "pathless_summary",
    }


def _observation_diagnostic_count(observation: Observation) -> int:
    if not isinstance(observation.data, dict):
        return 0
    diagnostics = observation.data.get("diagnostics") if isinstance(observation.data.get("diagnostics"), list) else []
    if diagnostics:
        return len(diagnostics)
    if observation.tool_name == "run_tests":
        summary = observation.data.get("test_summary") if isinstance(observation.data.get("test_summary"), dict) else {}
        failed = int(summary.get("failed") or 0)
        if failed:
            return failed
    if observation.tool_name == "report_quality":
        reasons = observation.data.get("reasons") if isinstance(observation.data.get("reasons"), list) else []
        if reasons:
            return len(reasons)
    return 1 if _diagnostic_detail(observation) else 0
