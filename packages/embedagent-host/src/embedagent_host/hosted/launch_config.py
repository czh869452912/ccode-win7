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
    approve_all: bool = False
    approve_writes: bool = False
    approve_commands: bool = False
    permission_rules: str = ""
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


def resolve_launch_config(
    workspace: str,
    overrides: LaunchOverrides,
    config_loader: Callable[[str], Any],
) -> LaunchConfig:
    resolved_workspace = os.path.realpath(workspace)
    app_config = config_loader(resolved_workspace)
    if overrides.max_context_tokens is not None:
        app_config.max_context_tokens = overrides.max_context_tokens
    if overrides.reserve_output_tokens is not None:
        app_config.reserve_output_tokens = overrides.reserve_output_tokens
    if overrides.chars_per_token is not None:
        app_config.chars_per_token = overrides.chars_per_token

    base_url = str(
        _first_non_empty(
            overrides.base_url,
            getattr(app_config, "base_url", ""),
            os.environ.get("EMBEDAGENT_BASE_URL"),
            "http://127.0.0.1:8000/v1",
        )
        or ""
    )
    api_key = str(
        _first_non_empty(
            overrides.api_key,
            getattr(app_config, "api_key", ""),
            os.environ.get("EMBEDAGENT_API_KEY"),
            "",
        )
        or ""
    )
    model = str(
        _first_non_empty(
            overrides.model,
            getattr(app_config, "model", ""),
            os.environ.get("EMBEDAGENT_MODEL"),
            "",
        )
        or ""
    )
    timeout = float(
        _first_non_empty(
            overrides.timeout,
            getattr(app_config, "timeout", None),
            os.environ.get("EMBEDAGENT_TIMEOUT"),
            120.0,
        )
    )
    if not model:
        raise ValueError("必须通过 --model、环境变量或配置文件提供模型名称。")
    agent_application_id = str(
        _first_non_empty(
            overrides.agent_application_id,
            getattr(app_config, "agent_application_id", ""),
            os.environ.get("EMBEDAGENT_AGENT_APPLICATION_ID"),
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
        approve_all=bool(overrides.approve_all),
        approve_writes=bool(overrides.approve_writes),
        approve_commands=bool(overrides.approve_commands),
        permission_rules=overrides.permission_rules or "",
        agent_application_id=agent_application_id,
    )
