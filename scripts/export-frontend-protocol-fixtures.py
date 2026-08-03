from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional

from embedagent_protocol import (
    AgentApplicationDescriptor,
    AppBootstrap,
    CapabilitySnapshot,
    CommandDescriptor,
    KeybindingDescriptor,
    ModeDescriptor,
    SessionBootstrap,
    SessionEventEnvelope,
    ShellDescriptor,
    SurfaceDescriptor,
    ThreadShell,
    ToolPresentation,
)


def build_app_bootstrap() -> Dict[str, Any]:
    shell = ShellDescriptor(
        schema_version=1,
        commands=[
            CommandDescriptor(
                id="session.new",
                label="New Session",
                group="session",
                dispatch={"kind": "session.create"},
            )
        ],
        surfaces=[
            SurfaceDescriptor(
                id="session.commands",
                label="Commands",
                placement="overlay",
                renderer_key="command_palette",
            )
        ],
        keybindings=[KeybindingDescriptor(command_id="session.new", keys="ctrl+n")],
    )
    return AppBootstrap(
        schema_version=1,
        app={"product_name": "EmbedAgent", "protocol": "app_shell_v1"},
        workspaces=[{"id": "workspace-1", "label": "Fixture", "path": "D:/fixture"}],
        active_workspace={"id": "workspace-1", "label": "Fixture", "path": "D:/fixture"},
        has_active_workspace=True,
        shell=shell,
        settings={"confirm_workspace_switch": True},
        diagnostics={"offline": True},
    ).to_dict()


def build_session_bootstrap() -> Dict[str, Any]:
    capabilities = CapabilitySnapshot(
        schema_version=1,
        modes=[
            ModeDescriptor(
                id="build",
                label="Build",
                description="Implement the current task",
                icon_key="hammer",
                color_token="success",
                command_id="mode.build",
            )
        ],
        commands=[
            CommandDescriptor(
                id="help",
                label="/help",
                group="builtin",
                dispatch={"kind": "session.command", "command": "/help"},
            )
        ],
        tools=[
            ToolPresentation(
                name="read_file",
                label="Read File",
                renderer_key="generic",
                permission_category="read",
            )
        ],
        agent_application=AgentApplicationDescriptor(
            id="embedagent.generic",
            label="Generic Agent",
            profile_id="embedagent.generic",
            active=True,
        ),
        agent_applications=[
            AgentApplicationDescriptor(
                id="embedagent.generic",
                label="Generic Agent",
                profile_id="embedagent.generic",
                active=True,
            )
        ],
        empty_state={"scenario_label": "Local workspace"},
    )
    return SessionBootstrap(
        schema_version=1,
        event_cursor=4,
        thread=ThreadShell(
            id="session-1",
            title="Fixture Session",
            archived=False,
            current_mode="build",
            status="idle",
            updated_at="2026-08-03T00:00:00Z",
        ),
        snapshot={
            "session_id": "session-1",
            "status": "idle",
            "current_mode": "build",
            "workflow_state": {},
        },
        activities=[],
        capabilities=capabilities,
        workflow={},
        plan=None,
        permission_context={"session_id": "session-1", "categories": []},
    ).to_dict()


def build_session_event() -> Dict[str, Any]:
    return SessionEventEnvelope(
        schema_version=1,
        event_id="event-5",
        session_id="session-1",
        sequence=5,
        event_kind="session.snapshot",
        timestamp="2026-08-03T00:00:01Z",
        payload={"snapshot": {"session_id": "session-1", "status": "idle"}},
    ).to_dict()


def write_fixture(output_dir: str, name: str, payload: Dict[str, Any]) -> None:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        handle.write("\n")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    write_fixture(args.output_dir, "app_bootstrap.json", build_app_bootstrap())
    write_fixture(args.output_dir, "session_bootstrap.json", build_session_bootstrap())
    write_fixture(args.output_dir, "session_event.json", build_session_event())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
