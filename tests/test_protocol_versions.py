import unittest

from embedagent_protocol import CapabilitySnapshot, SessionEventEnvelope, ShellDescriptor

from embedagent.frontend.gui.backend.protocol_versions import (
    AGENT_SESSION_PROTOCOL,
    APP_SHELL_PROTOCOL,
    CAPABILITY_PROTOCOL,
    IDE_SERVICE_PROTOCOL,
    make_protocol_envelope,
    validate_protocol_envelope,
)


class ProtocolVersionTests(unittest.TestCase):
    def test_protocol_versions_and_envelope_validation(self):
        self.assertEqual(AGENT_SESSION_PROTOCOL, "agent_session_v1")
        self.assertEqual(CAPABILITY_PROTOCOL, "capability_v1")
        self.assertEqual(IDE_SERVICE_PROTOCOL, "ide_service_v1")
        self.assertEqual(APP_SHELL_PROTOCOL, "app_shell_v1")

        envelope = make_protocol_envelope(
            AGENT_SESSION_PROTOCOL,
            {"unknown_activity": {"kind": "future"}},
            sequence=4,
            revision="rev-1",
        )
        result = validate_protocol_envelope(envelope, expected_protocol=AGENT_SESSION_PROTOCOL)

        self.assertTrue(result["valid"])
        self.assertEqual(result["envelope"]["payload"]["unknown_activity"]["kind"], "future")
        self.assertEqual(result["envelope"]["sequence"], 4)

        session_event = SessionEventEnvelope(
            schema_version=1,
            event_id="evt-1",
            session_id="s-1",
            sequence=1,
            event_kind="session.created",
            timestamp="2026-07-26T00:00:00Z",
            payload={},
        )
        self.assertEqual(session_event.to_dict()["schema_version"], 1)

    def test_frontend_protocol_dtos_require_current_schema_version(self):
        self.assertEqual(CapabilitySnapshot(schema_version=1).to_dict()["schema_version"], 1)
        self.assertEqual(ShellDescriptor(schema_version=1).to_dict()["schema_version"], 1)
        with self.assertRaises(ValueError):
            CapabilitySnapshot(schema_version=0)
        with self.assertRaises(ValueError):
            ShellDescriptor(schema_version=2)

    def test_protocol_envelope_rejects_bad_sequence_revision_and_sensitive_fields(self):
        result = validate_protocol_envelope(
            {
                "protocol": APP_SHELL_PROTOCOL,
                "version": 1,
                "sequence": True,
                "revision": "",
                "payload": {"api_key": "secret", "prompt": "hidden"},
            },
            expected_protocol=APP_SHELL_PROTOCOL,
        )

        self.assertFalse(result["valid"])
        self.assertIn("sequence", result["errors"])
        self.assertIn("revision", result["errors"])
        self.assertIn("sensitive", result["errors"])


if __name__ == "__main__":
    unittest.main()
