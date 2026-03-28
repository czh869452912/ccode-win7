from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from embedagent.artifacts import ArtifactStore
from embedagent.session import Observation, Session


_PYTHON_REQ_RE = re.compile(r'^requires-python\s*=\s*"([^"]+)"', re.MULTILINE)
_PRIMARY_ENV_RE = re.compile(r'Primary development environment manager:\s*`([^`]+)`')
_FALLBACK_ENV_RE = re.compile(r'approved fallback', re.IGNORECASE)


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + '...'


class ProjectMemoryStore(object):
    def __init__(
        self,
        workspace: str,
        relative_root: str = '.embedagent/memory/project',
        max_recipe_count: int = 12,
        max_issue_count: int = 12,
        max_seen_events: int = 512,
        max_resolved_issues: int = 6,
    ) -> None:
        self.workspace = os.path.realpath(workspace)
        self.relative_root = relative_root.replace('\\', '/')
        self.root = os.path.join(self.workspace, *self.relative_root.split('/'))
        self.profile_path = os.path.join(self.root, 'project-profile.json')
        self.recipes_path = os.path.join(self.root, 'command-recipes.json')
        self.issues_path = os.path.join(self.root, 'known-issues.json')
        self.index_path = os.path.join(self.root, 'memory-index.json')
        self.max_recipe_count = max_recipe_count
        self.max_issue_count = max_issue_count
        self.max_seen_events = max_seen_events
        self.max_resolved_issues = max_resolved_issues
        self.sanitizer = ArtifactStore(self.workspace)

    def refresh(
        self,
        session: Session,
        current_mode: str,
        session_summary_ref: Optional[str] = None,
    ) -> None:
        self._ensure_root()
        profile = self._load_json(self.profile_path, self._bootstrap_profile())
        recipes = self._load_json(self.recipes_path, [])
        issues = self._load_json(self.issues_path, [])
        index = self._load_json(self.index_path, {'processed_events': []})
        processed_events = list(index.get('processed_events') or [])
        processed_set = set(processed_events)

        self._update_profile(profile, session, current_mode, session_summary_ref)
        for event_id, action_name, arguments, observation in self._iter_events(session):
            if event_id in processed_set:
                continue
            self._apply_observation(recipes, issues, current_mode, action_name, arguments, observation)
            processed_events.append(event_id)
            processed_set.add(event_id)

        processed_events = processed_events[-self.max_seen_events :]
        recipes = self._normalize_recipes(recipes)
        issues = self._normalize_issues(issues)
        index = {
            'schema_version': 1,
            'updated_at': _utc_now(),
            'processed_events': processed_events,
        }
        self._write_json(self.profile_path, profile)
        self._write_json(self.recipes_path, recipes)
        self._write_json(self.issues_path, issues)
        self._write_json(self.index_path, index)


    def collect_artifact_refs(self) -> List[str]:
        issues = self._load_json(self.issues_path, [])
        refs = []
        seen = set()
        for item in issues:
            if not isinstance(item, dict):
                continue
            for path in item.get("artifact_refs") or []:
                if not path or path in seen:
                    continue
                seen.add(path)
                refs.append(path)
        return refs

    def cleanup(self) -> Dict[str, int]:
        self._ensure_root()
        recipes = self._load_json(self.recipes_path, [])
        issues = self._load_json(self.issues_path, [])
        normalized_recipes = self._normalize_recipes(recipes)
        normalized_issues = self._cleanup_issues(issues)
        self._write_json(self.recipes_path, normalized_recipes)
        self._write_json(self.issues_path, normalized_issues)
        return {
            "recipes": len(normalized_recipes),
            "issues": len(normalized_issues),
        }

    def build_system_message(self, mode_name: str, char_limit: int) -> Optional[str]:
        profile = self._load_json(self.profile_path, None)
        recipes = self._load_json(self.recipes_path, [])
        issues = self._load_json(self.issues_path, [])
        if not profile:
            return None
        lines = ['以下是项目级记忆，仅供当前任务参考；若与当前系统提示或用户明确要求冲突，以后者为准。']
        profile_line = self._profile_line(profile)
        if profile_line:
            lines.append('项目概况：%s' % profile_line)
        selected_recipes = self._select_recipes(mode_name, recipes)
        if selected_recipes:
            lines.append('常用命令：')
            for index, item in enumerate(selected_recipes, start=1):
                lines.append(
                    '%s. [%s] cwd=%s cmd=%s'
                    % (
                        index,
                        item.get('tool_name', ''),
                        item.get('cwd', '.'),
                        _truncate_text(item.get('command', ''), 120),
                    )
                )
        selected_issues = self._select_issues(mode_name, issues)
        if selected_issues:
            lines.append('已知问题：')
            for index, item in enumerate(selected_issues, start=1):
                parts = [item.get('tool_name', '')]
                if item.get('path'):
                    parts.append('path=%s' % item['path'])
                if item.get('summary'):
                    parts.append(_truncate_text(item['summary'], 120))
                if item.get('status'):
                    parts.append('status=%s' % item['status'])
                lines.append('%s. %s' % (index, ', '.join([part for part in parts if part])))
        text = '\n'.join(lines)
        return _truncate_text(text, char_limit) if text else None

    def _ensure_root(self) -> None:
        if not os.path.isdir(self.root):
            os.makedirs(self.root)

    def _bootstrap_profile(self) -> Dict[str, Any]:
        now = _utc_now()
        profile = {
            'schema_version': 1,
            'workspace_name': os.path.basename(self.workspace),
            'workspace_root': '.',
            'created_at': now,
            'updated_at': now,
            'requires_python': self._read_requires_python(),
            'primary_environment_manager': self._read_primary_environment_manager(),
            'fallback_environment_manager': 'conda' if self._has_conda_fallback() else None,
            'runtime_target_python': '3.8',
            'constraints': self._read_constraints(),
            'notes': [],
        }
        return profile

    def _update_profile(
        self,
        profile: Dict[str, Any],
        session: Session,
        current_mode: str,
        session_summary_ref: Optional[str],
    ) -> None:
        profile['updated_at'] = _utc_now()
        profile['last_session_id'] = session.session_id
        profile['last_mode'] = current_mode
        profile['last_summary_ref'] = session_summary_ref
        profile['turn_count'] = len(session.turns)
        profile['message_count'] = len(session.messages)
        if not profile.get('requires_python'):
            profile['requires_python'] = self._read_requires_python()
        if not profile.get('primary_environment_manager'):
            profile['primary_environment_manager'] = self._read_primary_environment_manager()
        if not profile.get('fallback_environment_manager') and self._has_conda_fallback():
            profile['fallback_environment_manager'] = 'conda'
        if not profile.get('constraints'):
            profile['constraints'] = self._read_constraints()

    def _iter_events(self, session: Session) -> List[Tuple[str, str, Dict[str, Any], Observation]]:
        items = []
        for turn in session.turns:
            for index, action in enumerate(turn.actions):
                if index >= len(turn.observations):
                    continue
                event_id = '%s:%s' % (session.session_id, action.call_id)
                items.append((event_id, action.name, action.arguments, turn.observations[index]))
        return items

    def _apply_observation(
        self,
        recipes: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
        current_mode: str,
        action_name: str,
        arguments: Dict[str, Any],
        observation: Observation,
    ) -> None:
        if observation.success:
            self._record_recipe(recipes, current_mode, action_name, arguments, observation)
            self._resolve_issues(issues, observation)
        else:
            self._record_issue(issues, current_mode, observation)

    def _record_recipe(
        self,
        recipes: List[Dict[str, Any]],
        current_mode: str,
        action_name: str,
        arguments: Dict[str, Any],
        observation: Observation,
    ) -> None:
        if action_name not in ('run_command', 'compile_project', 'run_tests', 'run_clang_tidy', 'run_clang_analyzer', 'collect_coverage'):
            return
        if not isinstance(observation.data, dict):
            return
        command = observation.data.get('command') or arguments.get('command')
        cwd = observation.data.get('cwd') or arguments.get('cwd') or '.'
        if not command:
            return
        key = '%s|%s|%s' % (action_name, cwd, command)
        now = _utc_now()
        for item in recipes:
            if item.get('key') != key:
                continue
            item['last_success_at'] = now
            item['success_count'] = int(item.get('success_count') or 0) + 1
            item['last_mode'] = current_mode
            return
        recipes.append(
            {
                'key': key,
                'tool_name': action_name,
                'command': command,
                'cwd': cwd,
                'last_mode': current_mode,
                'created_at': now,
                'last_success_at': now,
                'success_count': 1,
            }
        )

    def _record_issue(
        self,
        issues: List[Dict[str, Any]],
        current_mode: str,
        observation: Observation,
    ) -> None:
        if not isinstance(observation.data, dict):
            return
        summary = self._issue_summary(observation)
        if not summary:
            return
        key = self._issue_key(observation, summary)
        now = _utc_now()
        for item in issues:
            if item.get('key') != key:
                continue
            item['last_seen_at'] = now
            item['count'] = int(item.get('count') or 0) + 1
            item['status'] = 'open'
            item['mode_name'] = current_mode
            return
        issue = {
            'key': key,
            'tool_name': observation.tool_name,
            'mode_name': current_mode,
            'path': self._primary_path(observation),
            'command': self._primary_command(observation),
            'summary': summary,
            'status': 'open',
            'count': 1,
            'first_seen_at': now,
            'last_seen_at': now,
            'artifact_refs': self._artifact_refs(observation),
        }
        issues.append(issue)

    def _resolve_issues(self, issues: List[Dict[str, Any]], observation: Observation) -> None:
        tool_name = observation.tool_name
        path = self._primary_path(observation)
        command = self._primary_command(observation)
        if not path and not command:
            return
        for item in issues:
            if item.get('tool_name') != tool_name or item.get('status') != 'open':
                continue
            same_command = command and item.get('command') == command
            same_path = path and item.get('path') == path
            if same_command or same_path:
                item['status'] = 'resolved'
                item['resolved_at'] = _utc_now()


    def _cleanup_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        open_items = []
        resolved_items = []
        for item in issues:
            if not isinstance(item, dict):
                continue
            if item.get("status") == "open":
                open_items.append(item)
            else:
                resolved_items.append(item)
        open_items = sorted(
            open_items,
            key=lambda item: (item.get("last_seen_at") or "", int(item.get("count") or 0)),
            reverse=True,
        )
        resolved_items = sorted(
            resolved_items,
            key=lambda item: item.get("resolved_at") or item.get("last_seen_at") or "",
            reverse=True,
        )
        result = open_items[: self.max_issue_count]
        result.extend(resolved_items[: self.max_resolved_issues])
        return result[: self.max_issue_count + self.max_resolved_issues]

    def _normalize_recipes(self, recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        recipes = sorted(
            recipes,
            key=lambda item: (item.get('last_success_at') or '', int(item.get('success_count') or 0)),
            reverse=True,
        )
        return recipes[: self.max_recipe_count]

    def _normalize_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        issues = sorted(
            issues,
            key=lambda item: ((item.get('status') != 'open'), item.get('last_seen_at') or '', int(item.get('count') or 0)),
        )
        return issues[: self.max_issue_count]

    def _select_recipes(self, mode_name: str, recipes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        preferred = {
            'verify': ('compile_project', 'run_tests', 'run_clang_tidy', 'run_clang_analyzer', 'collect_coverage'),
            'test': ('run_tests', 'compile_project', 'collect_coverage'),
            'code': ('compile_project', 'run_command', 'run_tests'),
            'debug': ('run_command', 'compile_project', 'run_tests'),
        }.get(mode_name, ('compile_project', 'run_tests', 'run_command'))
        selected = []
        seen = set()
        for tool_name in preferred:
            for item in recipes:
                if item.get('tool_name') != tool_name or item.get('key') in seen:
                    continue
                selected.append(item)
                seen.add(item['key'])
                break
        return selected[:4]

    def _select_issues(self, mode_name: str, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        preferred = {
            'verify': ('compile_project', 'run_tests', 'run_clang_tidy', 'run_clang_analyzer', 'report_quality'),
            'test': ('run_tests', 'compile_project'),
            'code': ('compile_project', 'run_command', 'report_quality'),
            'debug': ('run_command', 'compile_project', 'run_tests'),
        }.get(mode_name, ())
        selected = []
        for item in issues:
            if item.get('status') != 'open':
                continue
            if preferred and item.get('tool_name') not in preferred:
                continue
            selected.append(item)
            if len(selected) >= 4:
                break
        return selected

    def _profile_line(self, profile: Dict[str, Any]) -> str:
        parts = [profile.get('workspace_name', '')]
        if profile.get('requires_python'):
            parts.append('python=%s' % profile['requires_python'])
        if profile.get('runtime_target_python'):
            parts.append('runtime=%s' % profile['runtime_target_python'])
        if profile.get('primary_environment_manager'):
            parts.append('env=%s' % profile['primary_environment_manager'])
        constraints = profile.get('constraints') or []
        if constraints:
            parts.append('constraints=%s' % ','.join(constraints[:3]))
        return '; '.join([part for part in parts if part])

    def _issue_summary(self, observation: Observation) -> str:
        if observation.error:
            return observation.error
        if isinstance(observation.data, dict):
            reasons = observation.data.get('reasons') or []
            if reasons:
                return str(reasons[0])
            diagnostics = observation.data.get('diagnostics') or []
            if diagnostics and isinstance(diagnostics[0], dict) and diagnostics[0].get('message'):
                return str(diagnostics[0]['message'])
        return ''

    def _issue_key(self, observation: Observation, summary: str) -> str:
        return '%s|%s|%s|%s' % (
            observation.tool_name,
            self._primary_path(observation) or '',
            self._primary_command(observation) or '',
            _truncate_text(summary, 120),
        )

    def _primary_path(self, observation: Observation) -> Optional[str]:
        if not isinstance(observation.data, dict):
            return None
        if observation.data.get('path'):
            return observation.data.get('path')
        diagnostics = observation.data.get('diagnostics') or []
        if diagnostics and isinstance(diagnostics[0], dict):
            return diagnostics[0].get('file')
        return None

    def _primary_command(self, observation: Observation) -> Optional[str]:
        if not isinstance(observation.data, dict):
            return None
        return observation.data.get('command')

    def _artifact_refs(self, observation: Observation) -> List[str]:
        if not isinstance(observation.data, dict):
            return []
        refs = []
        for key, value in observation.data.items():
            if key.endswith('_artifact_ref') and value:
                refs.append(value)
        return refs[:4]

    def _load_json(self, path: str, default: Any) -> Any:
        if not os.path.isfile(path):
            return default
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return default
        return data

    def _write_json(self, path: str, data: Any) -> None:
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(self.sanitizer.sanitize_jsonable(data), handle, ensure_ascii=False, indent=2, sort_keys=True)

    def _read_requires_python(self) -> Optional[str]:
        path = os.path.join(self.workspace, 'pyproject.toml')
        if not os.path.isfile(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                content = handle.read()
        except Exception:
            return None
        match = _PYTHON_REQ_RE.search(content)
        return match.group(1) if match else None

    def _read_primary_environment_manager(self) -> Optional[str]:
        content = self._read_agents_text()
        if not content:
            return None
        match = _PRIMARY_ENV_RE.search(content)
        return match.group(1) if match else None

    def _has_conda_fallback(self) -> bool:
        content = self._read_agents_text()
        if not content:
            return False
        return bool(_FALLBACK_ENV_RE.search(content)) and 'conda' in content.lower()

    def _read_constraints(self) -> List[str]:
        content = self._read_agents_text() or ''
        constraints = []
        if 'Windows 7 compatibility is mandatory.' in content:
            constraints.append('windows7')
        if 'Offline deployment is mandatory.' in content:
            constraints.append('offline')
        if 'zero external dependencies' in content.lower():
            constraints.append('self-contained')
        return constraints

    def _read_agents_text(self) -> Optional[str]:
        path = os.path.join(self.workspace, 'AGENTS.md')
        if not os.path.isfile(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                return handle.read()
        except Exception:
            return None
