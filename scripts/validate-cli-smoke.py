#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional

from embedagent.bundle_policy import load_bundle_policy
from embedagent.hosted import LaunchOverrides, create_hosted_runtime, resolve_launch_config


class _FakeOpenAIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        del format, args

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self.send_error(400)
            return
        if self.path.rstrip("/") != "/v1/chat/completions" or payload.get("stream"):
            self.send_error(404)
            return
        messages = payload.get("messages") or []
        user_text = self._last_user_message(messages)
        has_tool_result = self._has_tool_result_after_last_user(messages)
        response = self._completion_payload(user_text, has_tool_result)
        encoded = json.dumps(response, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def _last_user_message(messages):
        for item in reversed(messages):
            if item.get("role") == "user":
                return str(item.get("content") or "")
        return ""

    @staticmethod
    def _has_tool_result_after_last_user(messages):
        saw_tool = False
        for item in reversed(messages):
            if item.get("role") == "tool":
                saw_tool = True
            elif item.get("role") == "user":
                return saw_tool
        return False

    @classmethod
    def _completion_payload(cls, user_text, has_tool_result):
        tool_call = None if has_tool_result else cls._tool_call(user_text)
        if tool_call is not None:
            message = {
                "content": "",
                "tool_calls": [
                    {
                        "id": tool_call["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call["name"],
                            "arguments": json.dumps(
                                tool_call["arguments"],
                                ensure_ascii=True,
                                separators=(",", ":"),
                            ),
                        },
                    }
                ],
            }
            finish_reason = "tool_calls"
        else:
            message = {"content": "CLI smoke completed."}
            finish_reason = "stop"
        return {
            "choices": [
                {
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ]
        }

    @staticmethod
    def _tool_call(user_text):
        normalized = str(user_text or "").strip().lower()
        if normalized == "tool smoke":
            return {
                "id": "call-read",
                "name": "read_file",
                "arguments": {"path": "README.md"},
            }
        if normalized == "permission smoke":
            return {
                "id": "call-write",
                "name": "write_file",
                "arguments": {
                    "path": "permission-smoke.txt",
                    "content": "permission smoke completed\n",
                },
            }
        if normalized == "ask smoke":
            return {
                "id": "call-ask",
                "name": "ask_user",
                "arguments": {
                    "question": "Continue smoke validation?",
                    "option_1": "Continue",
                    "option_2": "Cancel",
                },
            }
        return None


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="ascii",
    )
    os.replace(str(temporary), str(path))


def _snapshot(host, session_id: str) -> Dict[str, object]:
    payload = host.get_session_bootstrap(session_id)
    snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
    if not isinstance(snapshot, dict):
        raise RuntimeError("invalid_session_bootstrap")
    return snapshot


def _wait_for_status(host, session_id: str, expected: str, timeout: float = 8.0):
    deadline = time.time() + timeout
    snapshot = _snapshot(host, session_id)
    while time.time() < deadline:
        if snapshot.get("status") == expected:
            return snapshot
        if snapshot.get("status") == "error":
            raise RuntimeError("session_error")
        time.sleep(0.05)
        snapshot = _snapshot(host, session_id)
    raise RuntimeError("session_status_timeout")


def _interaction_id(snapshot: Dict[str, object], expected_kind: str) -> str:
    pending = snapshot.get("pending_interaction")
    if not isinstance(pending, dict) or pending.get("kind") != expected_kind:
        raise RuntimeError("invalid_pending_interaction")
    interaction_id = str(pending.get("interaction_id") or "")
    if not interaction_id:
        raise RuntimeError("missing_interaction_id")
    return interaction_id


def _bundle_runtime_source(bundle_root: Path) -> str:
    expected = os.path.realpath(str(bundle_root / "runtime" / "python" / "python.exe"))
    actual = os.path.realpath(sys.executable)
    if os.path.normcase(actual) != os.path.normcase(expected):
        raise RuntimeError("python_runtime_outside_bundle")
    return "bundle"


def _run_smoke(bundle_root: Path, workspace: Path) -> Dict[str, object]:
    runtime_source = _bundle_runtime_source(bundle_root)
    policy = load_bundle_policy(str(bundle_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenAIHandler)
    server_thread = threading.Thread(target=server.serve_forever, name="cli-smoke-model")
    server_thread.daemon = True
    server_thread.start()
    events = []  # type: List[object]
    try:
        port = int(server.server_address[1])
        launch_config = resolve_launch_config(
            str(workspace),
            LaunchOverrides(
                base_url="http://127.0.0.1:%d/v1" % port,
                api_key="",
                model="cli-smoke-model",
                timeout=5.0,
                max_turns=4,
            ),
        )
        runtime = create_hosted_runtime(launch_config, event_handler=events.append)
        host = runtime.session_host
        created = host.create_session("build")
        session_id = str(created.get("session_id") or "")
        if not session_id:
            raise RuntimeError("session_create_failed")

        tool_snapshot = host.submit_user_message(
            session_id,
            "tool smoke",
            stream=False,
            wait=True,
        )
        tool_completed = bool(
            tool_snapshot.get("status") == "idle"
            and any(
                getattr(item, "event_kind", "") == "tool.finished"
                and bool(getattr(item, "payload", {}).get("success"))
                for item in events
            )
        )
        if not tool_completed:
            raise RuntimeError("read_tool_failed")

        host.submit_user_message(
            session_id,
            "permission smoke",
            stream=False,
            wait=False,
        )
        waiting_permission = _wait_for_status(host, session_id, "waiting_permission")
        host.respond_to_interaction(
            session_id,
            _interaction_id(waiting_permission, "permission"),
            {"decision": "accept"},
        )
        permission_snapshot = _wait_for_status(host, session_id, "idle")
        permission_completed = bool(
            permission_snapshot.get("status") == "idle"
            and (workspace / "permission-smoke.txt").is_file()
        )
        if not permission_completed:
            raise RuntimeError("permission_interaction_failed")

        host.submit_user_message(
            session_id,
            "ask smoke",
            stream=False,
            wait=False,
        )
        waiting_input = _wait_for_status(host, session_id, "waiting_user_input")
        host.respond_to_interaction(
            session_id,
            _interaction_id(waiting_input, "user_input"),
            {"answers": {"answer": "Continue"}},
        )
        input_snapshot = _wait_for_status(host, session_id, "idle")
        input_completed = input_snapshot.get("status") == "idle"
        if not input_completed:
            raise RuntimeError("user_input_interaction_failed")

        runtime = None
        restored_runtime = create_hosted_runtime(launch_config)
        restored = restored_runtime.session_host.resume_session(session_id, "build")
        restored_ok = str(restored.get("session_id") or "") == session_id
        if not restored_ok:
            raise RuntimeError("session_restore_failed")

        return {
            "agent_application_id": launch_config.agent_application_id,
            "flavor_id": policy.flavor_id,
            "ok": True,
            "permission_interaction_completed": permission_completed,
            "runtime_source": runtime_source,
            "schema_version": 1,
            "session_created": True,
            "session_restored": restored_ok,
            "tool_completed": tool_completed,
            "user_input_interaction_completed": input_completed,
        }
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the bundled CLI agent runtime.")
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--workspace", default="")
    parser.add_argument("--json-report", required=True)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    report_path = Path(os.path.realpath(args.json_report))
    bundle_root = Path(os.path.realpath(args.bundle_root))
    owned_workspace = ""
    stage = "initialize"
    try:
        os.environ["EMBEDAGENT_BUNDLE_ROOT"] = str(bundle_root)
        if args.workspace:
            workspace = Path(os.path.realpath(args.workspace))
            workspace.mkdir(parents=True, exist_ok=True)
        else:
            owned_workspace = tempfile.mkdtemp(prefix="embedagent-cli-smoke-")
            workspace = Path(owned_workspace)
        readme = workspace / "README.md"
        if not readme.is_file():
            readme.write_text("CLI smoke workspace\n", encoding="ascii")
        stage = "runtime"
        payload = _run_smoke(bundle_root, workspace)
        _write_json(report_path, payload)
        print("CLI smoke validation passed.")
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        _write_json(
            report_path,
            {
                "error_type": type(exc).__name__,
                "failure_stage": stage,
                "ok": False,
            },
        )
        print("CLI smoke validation failed at %s (%s)." % (stage, type(exc).__name__))
        return 1
    finally:
        if owned_workspace:
            shutil.rmtree(owned_workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
