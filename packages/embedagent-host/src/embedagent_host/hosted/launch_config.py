from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class LaunchOverrides(object):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[float] = None
    max_turns: Optional[int] = None
    approve_all: Optional[bool] = None
    approve_writes: Optional[bool] = None
    approve_commands: Optional[bool] = None
    permission_rules: Optional[str] = None
    max_context_tokens: Optional[int] = None
    reserve_output_tokens: Optional[int] = None
    chars_per_token: Optional[float] = None
    agent_application_id: Optional[str] = None


@dataclass
class LaunchConfig(object):
    workspace: str
    app_config: Any
    base_url: str
    api_key: str
    model: str
    timeout: float
    max_turns: Optional[int]
    approve_all: bool
    approve_writes: bool
    approve_commands: bool
    permission_rules: str
    agent_application_id: str


def _first_non_empty(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value
            continue
        return value
    return None


def _environment_bool(name: str) -> Optional[bool]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    normalized = raw.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    raise ValueError("%s must be a boolean" % name)


def _environment_number(name: str, converter):
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        return converter(raw)
    except (TypeError, ValueError):
        raise ValueError("%s has an invalid numeric value" % name)


def resolve_launch_config(
    workspace: str,
    overrides: LaunchOverrides,
    config_loader: Callable[[str], Any],
) -> LaunchConfig:
    resolved_workspace = os.path.realpath(workspace)
    app_config = config_loader(resolved_workspace)
    app_config.max_context_tokens = _first_non_empty(
        overrides.max_context_tokens,
        _environment_number("EMBEDAGENT_MAX_CONTEXT_TOKENS", int),
        getattr(app_config, "max_context_tokens", None),
    )
    app_config.reserve_output_tokens = _first_non_empty(
        overrides.reserve_output_tokens,
        _environment_number("EMBEDAGENT_RESERVE_OUTPUT_TOKENS", int),
        getattr(app_config, "reserve_output_tokens", None),
    )
    app_config.chars_per_token = _first_non_empty(
        overrides.chars_per_token,
        _environment_number("EMBEDAGENT_CHARS_PER_TOKEN", float),
        getattr(app_config, "chars_per_token", None),
    )

    base_url = str(
        _first_non_empty(
            overrides.base_url,
            os.environ.get("EMBEDAGENT_BASE_URL"),
            getattr(app_config, "base_url", ""),
            "http://127.0.0.1:8000/v1",
        )
        or ""
    )
    api_key = str(
        _first_non_empty(
            overrides.api_key,
            os.environ.get("EMBEDAGENT_API_KEY"),
            getattr(app_config, "api_key", ""),
            "",
        )
        or ""
    )
    model = str(
        _first_non_empty(
            overrides.model,
            os.environ.get("EMBEDAGENT_MODEL"),
            getattr(app_config, "model", ""),
            "",
        )
        or ""
    )
    timeout = float(
        _first_non_empty(
            overrides.timeout,
            _environment_number("EMBEDAGENT_TIMEOUT", float),
            getattr(app_config, "timeout", None),
            120.0,
        )
    )
    if not model:
        raise ValueError("必须通过 --model、环境变量或配置文件提供模型名称。")
    agent_application_id = str(
        _first_non_empty(
            overrides.agent_application_id,
            os.environ.get("EMBEDAGENT_AGENT_APPLICATION_ID"),
            getattr(app_config, "agent_application_id", ""),
            "",
        )
        or ""
    )
    return LaunchConfig(
        workspace=resolved_workspace,
        app_config=app_config,
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
        max_turns=int(overrides.max_turns) if overrides.max_turns is not None else None,
        approve_all=bool(
            _first_non_empty(
                overrides.approve_all,
                _environment_bool("EMBEDAGENT_APPROVE_ALL"),
                getattr(app_config, "approve_all", None),
                False,
            )
        ),
        approve_writes=bool(
            _first_non_empty(
                overrides.approve_writes,
                _environment_bool("EMBEDAGENT_APPROVE_WRITES"),
                getattr(app_config, "approve_writes", None),
                False,
            )
        ),
        approve_commands=bool(
            _first_non_empty(
                overrides.approve_commands,
                _environment_bool("EMBEDAGENT_APPROVE_COMMANDS"),
                getattr(app_config, "approve_commands", None),
                False,
            )
        ),
        permission_rules=str(
            _first_non_empty(
                overrides.permission_rules,
                os.environ.get("EMBEDAGENT_PERMISSION_RULES"),
                getattr(app_config, "permission_rules", ""),
                "",
            )
            or ""
        ),
        agent_application_id=agent_application_id,
    )
