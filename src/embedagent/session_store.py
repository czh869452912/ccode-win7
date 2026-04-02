from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional


def _atomic_write_json(path: str, payload: Any) -> None:
    """Write *payload* to *path* atomically (write temp, rename).

    On NTFS (Windows 7) and POSIX, ``os.replace`` is atomic within the same
    filesystem, which prevents corrupt files on process crash.
    """
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)

from embedagent.artifacts import ArtifactStore
from embedagent.modes import build_system_prompt
from embedagent.session import Action, Observation, Session
from embedagent.workspace_profile import build_workspace_profile_message


_MODE_RE = re.compile(r"当前模式：(\w+)")


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


class SessionSummaryStore(object):
    def __init__(
        self,
        workspace: str,
        relative_root: str = ".embedagent/memory/sessions",
        working_set_limit: int = 12,
        modified_files_limit: int = 12,
        recent_actions_limit: int = 8,
        recent_artifacts_limit: int = 8,
        max_index_entries: int = 64,
        max_retained_sessions: int = 16,
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))
        self.index_path = os.path.join(self.root, "index.json")
        self.working_set_limit = working_set_limit
        self.modified_files_limit = modified_files_limit
        self.recent_actions_limit = recent_actions_limit
        self.recent_artifacts_limit = recent_artifacts_limit
        self.max_index_entries = max_index_entries
        self.max_retained_sessions = max_retained_sessions
        self.sanitizer = ArtifactStore(self.workspace)

    def persist(
        self,
        session: Session,
        current_mode: str,
        context_result: Optional[Any] = None,
    ) -> str:
        directory = os.path.join(self.root, session.session_id)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        summary_path = os.path.join(directory, "summary.json")
        previous = self._read_json(summary_path)
        payload = self._build_payload(session, current_mode, context_result)
        if context_result is None and previous is not None:
            for key in (
                "context_policy",
                "context_budget",
                "context_stats",
                "context_analysis",
                "compact_summary_text",
                "context_replacements",
                "context_pipeline_steps",
                "workspace_intelligence",
            ):
                if key in previous and key not in payload:
                    payload[key] = previous[key]
        _atomic_write_json(summary_path, payload)
        summary_ref = os.path.relpath(summary_path, self.workspace).replace(os.sep, "/")
        self._update_index(payload, summary_ref)
        return summary_ref

    def list_summaries(self, limit: int = 10) -> List[Dict[str, Any]]:
        index = self._read_json(self.index_path)
        items = []
        if isinstance(index, dict):
            items = index.get("sessions") or []
        if not items:
            items = self._scan_summaries()
        normalized = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            normalized.append(item)
        return normalized


    def collect_artifact_refs(self, limit_sessions: Optional[int] = None) -> List[str]:
        refs = []
        seen = set()
        summaries = self.list_summaries(limit=limit_sessions or self.max_retained_sessions)
        for item in summaries:
            summary_ref = item.get("summary_ref") if isinstance(item, dict) else None
            if not summary_ref:
                continue
            payload = self.load_summary(str(summary_ref))
            refs.extend(self._artifact_refs_from_summary(payload, seen))
        return refs

    def cleanup(self, max_sessions: Optional[int] = None) -> Dict[str, int]:
        keep_count = max_sessions or self.max_retained_sessions
        summaries = self.list_summaries(limit=self.max_index_entries)
        keep = []
        keep_ids = set()
        for item in summaries:
            if not isinstance(item, dict):
                continue
            session_id = item.get("session_id")
            if not session_id or session_id in keep_ids:
                continue
            if len(keep) < keep_count:
                keep.append(item)
                keep_ids.add(session_id)
        deleted = 0
        if os.path.isdir(self.root):
            for name in os.listdir(self.root):
                candidate = os.path.join(self.root, name)
                if name == "index.json" or not os.path.isdir(candidate):
                    continue
                if name in keep_ids:
                    continue
                try:
                    shutil.rmtree(candidate)
                    deleted += 1
                except OSError:
                    pass
        payload = {
            "schema_version": 1,
            "updated_at": _utc_now(),
            "sessions": keep,
        }
        directory = os.path.dirname(self.index_path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        _atomic_write_json(self.index_path, self.sanitizer.sanitize_jsonable(payload))
        return {"kept": len(keep), "deleted": deleted}

    def load_summary(self, reference: str) -> Dict[str, Any]:
        summary_path = self.resolve_summary_path(reference)
        payload = self._read_json(summary_path)
        if not isinstance(payload, dict):
            raise ValueError("未找到可用的会话摘要：%s" % reference)
        payload["summary_ref"] = os.path.relpath(summary_path, self.workspace).replace(os.sep, "/")
        return payload

    def resolve_summary_path(self, reference: str) -> str:
        raw = (reference or "").strip()
        if not raw:
            raise ValueError("恢复会话时必须提供 session_id、latest 或 summary.json 路径。")
        if raw == "latest":
            summaries = self.list_summaries(limit=1)
            if not summaries:
                raise ValueError("当前没有可恢复的会话摘要。")
            candidate = summaries[0].get("summary_ref") or summaries[0].get("path")
            if not candidate:
                raise ValueError("最近会话摘要缺少路径信息。")
            raw = str(candidate)
        if raw.endswith("summary.json"):
            candidate = raw
            if not os.path.isabs(candidate):
                candidate = os.path.join(self.workspace, candidate)
            candidate = os.path.realpath(candidate)
            if not os.path.isfile(candidate):
                raise ValueError("摘要文件不存在：%s" % reference)
            return candidate
        candidate = os.path.join(self.root, raw, "summary.json")
        candidate = os.path.realpath(candidate)
        if not os.path.isfile(candidate):
            raise ValueError("未找到会话摘要：%s" % reference)
        return candidate

    def build_resume_message(self, summary: Dict[str, Any], char_limit: int = 1800) -> str:
        lines = [
            "以下是上次会话的恢复摘要，仅供续跑参考；若与新的系统提示、项目记忆或用户当前要求冲突，以后者为准。"
        ]
        if summary.get("session_id"):
            lines.append("会话ID：%s" % summary["session_id"])
        if summary.get("summary_text"):
            lines.append("摘要：%s" % summary["summary_text"])
        if summary.get("working_set"):
            lines.append("工作集：%s" % ", ".join(summary["working_set"][:6]))
        if summary.get("modified_files"):
            lines.append("已修改：%s" % ", ".join(summary["modified_files"][:6]))
        if summary.get("last_success"):
            lines.append("最近成功：%s" % self._observation_line(summary["last_success"]))
        if summary.get("last_blocker"):
            lines.append("最近阻塞：%s" % self._observation_line(summary["last_blocker"]))
        if summary.get("recent_actions"):
            names = [item.get("name", "") for item in summary["recent_actions"] if item.get("name")]
            if names:
                lines.append("近期动作：%s" % ", ".join(names[:6]))
        if summary.get("recent_artifacts"):
            refs = [item.get("path", "") for item in summary["recent_artifacts"] if item.get("path")]
            if refs:
                lines.append("最近工件：%s" % ", ".join(refs[:4]))
        return _truncate_text("\n".join(lines), char_limit)

    def create_resumed_session(
        self,
        summary: Dict[str, Any],
        mode_name: Optional[str] = None,
        config: Optional[Any] = None,
    ) -> Session:
        current_mode = str(mode_name or summary.get("current_mode") or "code")
        session = Session(
            session_id=str(summary.get("session_id") or Session().session_id),
            started_at=str(summary.get("started_at") or _utc_now()),
        )
        resume_message = self.build_resume_message(summary)
        if resume_message:
            session.add_system_message(resume_message)
        session.add_system_message(build_workspace_profile_message(self.workspace, session.session_id))
        session.add_system_message(build_system_prompt(current_mode, config, self.workspace))
        return session

    def _read_json(self, path: str) -> Optional[Dict[str, Any]]:
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _update_index(self, payload: Dict[str, Any], summary_ref: str) -> None:
        directory = os.path.dirname(self.index_path)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        index = self._read_json(self.index_path) or {}
        sessions = index.get("sessions") if isinstance(index.get("sessions"), list) else []
        record = {
            "session_id": payload.get("session_id"),
            "started_at": payload.get("started_at"),
            "updated_at": payload.get("updated_at"),
            "current_mode": payload.get("current_mode"),
            "turn_count": payload.get("turn_count"),
            "message_count": payload.get("message_count"),
            "user_goal": payload.get("user_goal"),
            "summary_text": payload.get("summary_text"),
            "summary_ref": summary_ref,
        }
        updated = [item for item in sessions if item.get("session_id") != record["session_id"]]
        updated.append(record)
        updated.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        payload = {
            "schema_version": 1,
            "updated_at": _utc_now(),
            "sessions": updated[: self.max_index_entries],
        }
        _atomic_write_json(self.index_path, self.sanitizer.sanitize_jsonable(payload))

    def _scan_summaries(self) -> List[Dict[str, Any]]:
        if not os.path.isdir(self.root):
            return []
        records = []
        for session_id in os.listdir(self.root):
            if session_id == "index.json":
                continue
            summary_path = os.path.join(self.root, session_id, "summary.json")
            payload = self._read_json(summary_path)
            if not payload:
                continue
            records.append(
                {
                    "session_id": payload.get("session_id") or session_id,
                    "started_at": payload.get("started_at"),
                    "updated_at": payload.get("updated_at"),
                    "current_mode": payload.get("current_mode"),
                    "turn_count": payload.get("turn_count"),
                    "message_count": payload.get("message_count"),
                    "user_goal": payload.get("user_goal"),
                    "summary_text": payload.get("summary_text"),
                    "summary_ref": os.path.relpath(summary_path, self.workspace).replace(os.sep, "/"),
                }
            )
        records.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return records


    def _artifact_refs_from_summary(self, payload: Dict[str, Any], seen: set) -> List[str]:
        refs = []
        for item in payload.get("recent_artifacts") or []:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if not path or path in seen:
                continue
            seen.add(path)
            refs.append(path)
        for key in ("last_success", "last_blocker"):
            snapshot = payload.get(key)
            if not isinstance(snapshot, dict):
                continue
            for path in snapshot.get("artifact_refs") or []:
                if not path or path in seen:
                    continue
                seen.add(path)
                refs.append(path)
        return refs

    def _build_payload(
        self,
        session: Session,
        current_mode: str,
        context_result: Optional[Any],
    ) -> Dict[str, Any]:
        observations = self._all_observations(session)
        recent_actions = self._collect_recent_actions(session)
        working_set = self._collect_working_set(observations)
        modified_files = self._collect_modified_files(observations)
        last_success = self._find_last_observation(observations, True)
        last_blocker = self._find_last_observation(observations, False)
        mode_history = self._collect_mode_history(session, current_mode)
        recent_artifacts = self._collect_recent_artifacts(observations)
        payload = {
            "schema_version": 1,
            "session_id": session.session_id,
            "started_at": session.started_at,
            "updated_at": _utc_now(),
            "current_mode": current_mode,
            "turn_count": len(session.turns),
            "message_count": len(session.messages),
            "user_goal": self._first_user_message(session),
            "latest_user_message": self._last_user_message(session),
            "assistant_last_reply": self._last_assistant_message(session),
            "working_set": working_set,
            "modified_files": modified_files,
            "recent_actions": recent_actions,
            "mode_history": mode_history,
            "last_success": self._observation_snapshot(last_success),
            "last_blocker": self._observation_snapshot(last_blocker),
            "recent_artifacts": recent_artifacts,
        }
        transition_snapshot = self._transition_payload(session)
        if transition_snapshot:
            payload.update(transition_snapshot)
        context_payload = self._context_payload(context_result)
        if context_payload:
            payload.update(context_payload)
        payload["summary_text"] = self._build_summary_text(payload)
        return self.sanitizer.sanitize_jsonable(payload)

    def _context_payload(self, context_result: Optional[Any]) -> Dict[str, Any]:
        if context_result is None:
            return {}
        payload = {}
        policy = getattr(context_result, "policy", None)
        if policy is not None:
            payload["context_policy"] = {
                "mode_name": getattr(policy, "mode_name", None),
                "max_context_tokens": getattr(policy, "max_context_tokens", None),
                "reserve_output_tokens": getattr(policy, "reserve_output_tokens", None),
                "reserve_reasoning_tokens": getattr(policy, "reserve_reasoning_tokens", None),
                "max_recent_turns": getattr(policy, "max_recent_turns", None),
                "max_summary_turns": getattr(policy, "max_summary_turns", None),
            }
        budget = getattr(context_result, "budget", None)
        if budget is not None:
            payload["context_budget"] = {
                "max_input_tokens": getattr(budget, "max_input_tokens", None),
                "input_tokens": getattr(budget, "input_tokens", None),
                "remaining_input_tokens": getattr(budget, "remaining_input_tokens", None),
                "over_budget": getattr(budget, "over_budget", None),
            }
        stats = getattr(context_result, "stats", None)
        if stats is not None:
            payload["context_stats"] = {
                "recent_turns": getattr(stats, "recent_turns", None),
                "summarized_turns": getattr(stats, "summarized_turns", None),
                "reduced_tool_messages": getattr(stats, "reduced_tool_messages", None),
                "characters_before": getattr(stats, "characters_before", None),
                "characters_after": getattr(stats, "characters_after", None),
                "approx_tokens_before": getattr(stats, "approx_tokens_before", None),
                "approx_tokens_after": getattr(stats, "approx_tokens_after", None),
                "hard_trimmed": getattr(stats, "hard_trimmed", None),
            }
        analysis = getattr(context_result, "analysis", None)
        if isinstance(analysis, dict) and analysis:
            payload["context_analysis"] = {
                "tool_request_tokens": analysis.get("tool_request_tokens"),
                "tool_result_tokens": analysis.get("tool_result_tokens"),
                "duplicate_file_read_tokens": analysis.get("duplicate_file_read_tokens"),
                "artifact_replacement_count": analysis.get("artifact_replacement_count"),
                "resume_replay_hits": analysis.get("resume_replay_hits"),
                "top_hot_files": analysis.get("top_hot_files") or [],
            }
        summary_message = str(getattr(context_result, "summary_message", "") or "").strip()
        if summary_message:
            payload["compact_summary_text"] = summary_message
        replacements = getattr(context_result, "replacements", None)
        if isinstance(replacements, list) and replacements:
            payload["context_replacements"] = replacements[:8]
        pipeline_steps = getattr(context_result, "pipeline_steps", None)
        if isinstance(pipeline_steps, list) and pipeline_steps:
            payload["context_pipeline_steps"] = [str(item) for item in pipeline_steps[:12]]
        intelligence_sections = getattr(context_result, "intelligence_sections", None)
        if isinstance(intelligence_sections, list) and intelligence_sections:
            payload["workspace_intelligence"] = self.sanitizer.sanitize_jsonable(intelligence_sections[:8])
        return payload

    def _build_summary_text(self, payload: Dict[str, Any]) -> str:
        parts = []
        if payload.get("user_goal"):
            parts.append("目标：%s" % payload["user_goal"])
        parts.append("当前模式：%s" % payload.get("current_mode"))
        if payload.get("working_set"):
            parts.append("工作集：%s" % ", ".join(payload["working_set"][:5]))
        if payload.get("modified_files"):
            parts.append("已修改：%s" % ", ".join(payload["modified_files"][:5]))
        if payload.get("last_success"):
            parts.append("最近成功：%s" % self._observation_line(payload["last_success"]))
        if payload.get("last_blocker"):
            parts.append("最近阻塞：%s" % self._observation_line(payload["last_blocker"]))
        if payload.get("recent_actions"):
            names = [item.get("name", "") for item in payload["recent_actions"] if item.get("name")]
            if names:
                parts.append("近期动作：%s" % ", ".join(names[:6]))
        analysis = payload.get("context_analysis") if isinstance(payload.get("context_analysis"), dict) else {}
        if analysis.get("artifact_replacement_count"):
            parts.append("替换输出：%s" % analysis.get("artifact_replacement_count"))
        if payload.get("compact_retry_count"):
            parts.append("compact_retry：%s" % payload.get("compact_retry_count"))
        if payload.get("last_transition_reason") and payload.get("last_transition_reason") != "completed":
            parts.append("最后状态：%s" % payload.get("last_transition_reason"))
        if payload.get("compact_summary_text"):
            parts.append("compact：已生成摘要")
        return "；".join(parts)

    def _observation_line(self, snapshot: Dict[str, Any]) -> str:
        parts = [snapshot.get("tool_name", "")]
        if snapshot.get("path"):
            parts.append("path=%s" % snapshot["path"])
        if snapshot.get("command"):
            parts.append("cmd=%s" % _truncate_text(snapshot["command"], 80))
        if snapshot.get("exit_code") is not None:
            parts.append("exit=%s" % snapshot["exit_code"])
        if snapshot.get("error"):
            parts.append(_truncate_text(snapshot["error"], 80))
        return ", ".join([item for item in parts if item])

    def _first_user_message(self, session: Session) -> str:
        for turn in session.turns:
            if turn.user_message:
                return _truncate_text(turn.user_message, 240)
        return ""

    def _last_user_message(self, session: Session) -> str:
        for turn in reversed(session.turns):
            if turn.user_message:
                return _truncate_text(turn.user_message, 240)
        return ""

    def _last_assistant_message(self, session: Session) -> str:
        for turn in reversed(session.turns):
            if turn.assistant_message:
                return _truncate_text(turn.assistant_message, 240)
        return ""

    def _all_observations(self, session: Session) -> List[Observation]:
        observations = []
        for turn in session.turns:
            observations.extend(turn.observations)
        return observations

    def _transition_payload(self, session: Session) -> Dict[str, Any]:
        reasons = []
        messages = []
        for turn in session.turns:
            for transition in turn.transitions:
                reason = str(getattr(transition, "reason", "") or "").strip()
                message = str(getattr(transition, "message", "") or "").strip()
                if reason:
                    reasons.append(reason)
                    messages.append(message)
        if not reasons:
            return {}
        compact_retry_count = len([item for item in reasons if item == "compact_retry"])
        return {
            "last_transition_reason": reasons[-1],
            "last_transition_message": messages[-1] if messages else "",
            "recent_transition_reasons": reasons[-8:],
            "compact_retry_count": compact_retry_count,
        }

    def _collect_recent_actions(self, session: Session) -> List[Dict[str, Any]]:
        items = []
        for turn in session.turns:
            for index, action in enumerate(turn.actions):
                observation = turn.observations[index] if index < len(turn.observations) else None
                items.append(self._action_snapshot(action, observation))
        return items[-self.recent_actions_limit :]

    def _action_snapshot(self, action: Action, observation: Optional[Observation]) -> Dict[str, Any]:
        snapshot = {
            "name": action.name,
            "arguments": self._compact_arguments(action.arguments),
        }
        if observation is not None:
            snapshot["success"] = observation.success
            snapshot["error"] = observation.error
            if isinstance(observation.data, dict):
                snapshot["path"] = observation.data.get("path")
                snapshot["command"] = observation.data.get("command")
                snapshot["exit_code"] = observation.data.get("exit_code")
        return snapshot

    def _compact_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        compact = {}
        for key, value in arguments.items():
            if isinstance(value, str):
                compact[key] = _truncate_text(value, 120)
            else:
                compact[key] = value
        return compact

    def _collect_working_set(self, observations: List[Observation]) -> List[str]:
        result = []
        seen = set()
        for observation in reversed(observations):
            for path in self._paths_from_observation(observation):
                if path in seen or path == ".":
                    continue
                seen.add(path)
                result.append(path)
                if len(result) >= self.working_set_limit:
                    return result
        return result

    def _collect_modified_files(self, observations: List[Observation]) -> List[str]:
        result = []
        seen = set()
        for observation in observations:
            if observation.tool_name not in ("edit_file", "write_file") or not observation.success:
                continue
            path = observation.data.get("path") if isinstance(observation.data, dict) else None
            if not path or path in seen:
                continue
            seen.add(path)
            result.append(path)
            if len(result) >= self.modified_files_limit:
                break
        return result

    def _collect_mode_history(self, session: Session, current_mode: str) -> List[str]:
        history = []
        seen = set()
        for message in session.messages:
            if message.role != "system" or not message.content:
                continue
            match = _MODE_RE.search(message.content)
            if not match:
                continue
            mode_name = match.group(1)
            if mode_name in seen:
                continue
            seen.add(mode_name)
            history.append(mode_name)
        for turn in session.turns:
            for observation in turn.observations:
                if observation.tool_name != "switch_mode" or not observation.success:
                    continue
                if not isinstance(observation.data, dict):
                    continue
                to_mode = observation.data.get("to_mode")
                if to_mode and to_mode not in seen:
                    seen.add(to_mode)
                    history.append(to_mode)
        if current_mode not in seen:
            history.append(current_mode)
        return history[-6:]

    def _collect_recent_artifacts(self, observations: List[Observation]) -> List[Dict[str, Any]]:
        artifacts = []
        for observation in reversed(observations):
            if not isinstance(observation.data, dict):
                continue
            for key, value in observation.data.items():
                if not key.endswith("_artifact_ref") or not value:
                    continue
                artifacts.append(
                    {
                        "tool_name": observation.tool_name,
                        "field": key[:-13],
                        "path": value,
                    }
                )
                if len(artifacts) >= self.recent_artifacts_limit:
                    return artifacts
        return artifacts

    def _find_last_observation(
        self,
        observations: List[Observation],
        success: bool,
    ) -> Optional[Observation]:
        for observation in reversed(observations):
            if observation.success == success:
                return observation
        return None

    def _observation_snapshot(self, observation: Optional[Observation]) -> Optional[Dict[str, Any]]:
        if observation is None:
            return None
        snapshot = {
            "tool_name": observation.tool_name,
            "success": observation.success,
            "error": observation.error,
        }
        if isinstance(observation.data, dict):
            for key in (
                "path",
                "command",
                "cwd",
                "exit_code",
                "duration_ms",
                "error_count",
                "warning_count",
                "diagnostic_count",
                "line_coverage",
                "passed",
                "error_kind",
                "retryable",
                "blocked_by",
                "suggested_next_step",
            ):
                if key in observation.data:
                    snapshot[key] = observation.data[key]
            artifacts = []
            for key, value in observation.data.items():
                if key.endswith("_artifact_ref") and value:
                    artifacts.append(value)
            if artifacts:
                snapshot["artifact_refs"] = artifacts[:4]
        return snapshot

    def _paths_from_observation(self, observation: Observation) -> List[str]:
        if not isinstance(observation.data, dict):
            return []
        data = observation.data
        paths = []
        direct_path = data.get("path")
        if isinstance(direct_path, str) and direct_path:
            paths.append(direct_path)
        for key in ("matches", "entries", "diagnostics"):
            for item in data.get(key) or []:
                if not isinstance(item, dict):
                    continue
                candidate = item.get("path") or item.get("file")
                if isinstance(candidate, str) and candidate:
                    paths.append(candidate)
        for item in data.get("files") or []:
            if isinstance(item, str) and item:
                paths.append(item)
        unique = []
        seen = set()
        for item in paths:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique
