from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from embedagent.hosted import LaunchOverrides


@dataclass(frozen=True)
class CliLaunchOptions(object):
    workspace: str
    base_url: Optional[str] = None
    api_key: Optional[str] = field(default=None, repr=False)
    model: Optional[str] = None
    timeout: Optional[float] = None
    max_turns: Optional[int] = None
    approve_all: Optional[bool] = None
    approve_writes: Optional[bool] = None
    approve_commands: Optional[bool] = None
    permission_rules: Optional[str] = None
    agent_application_id: Optional[str] = None
    max_context_tokens: Optional[int] = None
    reserve_output_tokens: Optional[int] = None
    chars_per_token: Optional[float] = None

    def to_overrides(self) -> LaunchOverrides:
        return LaunchOverrides(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            timeout=self.timeout,
            max_turns=self.max_turns,
            approve_all=self.approve_all,
            approve_writes=self.approve_writes,
            approve_commands=self.approve_commands,
            permission_rules=self.permission_rules,
            agent_application_id=self.agent_application_id,
            max_context_tokens=self.max_context_tokens,
            reserve_output_tokens=self.reserve_output_tokens,
            chars_per_token=self.chars_per_token,
        )


@dataclass(frozen=True)
class CliOptions(object):
    command: str
    launch: CliLaunchOptions
    mode: str = ""
    resume: str = ""
    output: str = "text"
    task: str = ""
    sessions_action: str = ""
    reference: str = ""
    title: str = ""
    limit: int = 10
