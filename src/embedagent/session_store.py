from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from embedagent.artifacts import ArtifactStore
from embedagent.session import Action, Observation, Session


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
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace("\\", "/")
        self.root = os.path.join(self.workspace, *self.relative_root.split("/"))
        self.working_set_limit = working_set_limit
        self.modified_files_limit = modified_files_limit
        self.recent_actions_limit = recent_actions_limit
        self.recent_artifacts_limit = recent_artifacts_limit
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
        previous = self._read_previous_summary(summary_path)
        payload = self._build_payload(session, current_mode, context_result)
        if context_result is None and previous is not None:
            for key in ("context_policy", "context_budget", "context_stats"):
                if key in previous and key not in payload:
                    payload[key] = previous[key]
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        return os.path.relpath(summary_path, self.workspace).replace(os.sep, "/")

    def _read_previous_summary(self, summary_path: str) -> Optional[Dict[str, Any]]:
        if not os.path.isfile(summary_path):
            return None
        try:
            with open(summary_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

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
            if observation.tool_name != "edit_file" or not observation.success:
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
