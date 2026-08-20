from __future__ import annotations

import pytest

from embedagent_protocol import (
    AppBootstrap,
    FailureRecord,
    InteractionProjection,
    SessionEventEnvelope,
    ShellDescriptor,
    WorkspaceChangedNotification,
)
from embedagent_protocol.versions import FRONTEND_PROTOCOL_SCHEMA_VERSION


def test_frontend_protocol_uses_v2_and_app_bootstrap_has_structured_failure():
    failure = FailureRecord(
        code="configuration_error",
        source="cli",
        phase="application_composition",
        kind="configuration",
        safe_message="Application composition is incomplete.",
    )
    payload = AppBootstrap(
        schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION,
        app={"name": "EmbedAgent"},
        workspaces=[],
        shell=ShellDescriptor(schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION),
        last_failure=failure,
    ).to_dict()

    assert FRONTEND_PROTOCOL_SCHEMA_VERSION == 2
    assert payload["last_failure"] == failure.to_dict()
    assert "last_error" not in payload
    assert AppBootstrap(
        schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION,
        app={"name": "EmbedAgent"},
        workspaces=[],
        shell=ShellDescriptor(schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION),
        last_failure=failure,
    ).last_failure == failure


def test_app_bootstrap_rejects_legacy_last_error_wire_field():
    with pytest.raises(TypeError):
        AppBootstrap(
            schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION,
            app={"name": "EmbedAgent"},
            workspaces=[],
            shell=ShellDescriptor(schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION),
            last_error="legacy",
        )


def test_interaction_projection_is_minimal_and_json_safe():
    projection = InteractionProjection(
        kind="permission",
        interaction_id="approval-1",
        turn_id="turn-1",
        renderer="interaction",
        descriptor_version=1,
        descriptor={"choices": ["accept", "decline"], "default": "decline"},
    )

    payload = projection.to_dict()

    assert payload == {
        "kind": "permission",
        "interaction_id": "approval-1",
        "turn_id": "turn-1",
        "renderer": "interaction",
        "descriptor_version": 1,
        "descriptor": {"choices": ["accept", "decline"], "default": "decline"},
    }
    assert "session_id" not in payload


def test_workspace_changed_notification_is_not_a_session_event():
    notification = WorkspaceChangedNotification(
        schema_version=FRONTEND_PROTOCOL_SCHEMA_VERSION,
        workspace_id="workspace-1",
        path="C:/workspace",
        reason="activate",
    )

    payload = notification.to_dict()

    assert payload["schema_version"] == FRONTEND_PROTOCOL_SCHEMA_VERSION
    assert "sequence" not in payload
    assert WorkspaceChangedNotification.from_dict(payload) == notification
    with pytest.raises(TypeError):
        SessionEventEnvelope.from_dict(payload)
