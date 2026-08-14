#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_SCENARIO_IDS = (
    "run_json",
    "chat_completion",
    "chat_permission",
    "chat_user_input",
    "sessions_list",
    "sessions_show",
    "run_resume",
    "blocked_permission",
    "blocked_user_input",
)


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
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_error(404)
            return
        messages = payload.get("messages") or []
        user_text = self._last_user_message(messages)
        has_tool_result = self._has_tool_result_after_last_user(messages)
        completion = self._completion_payload(user_text, has_tool_result)
        if payload.get("stream"):
            self._send_stream(completion)
        else:
            self._send_json(completion)

    def _send_json(self, payload):
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_stream(self, completion):
        choice = completion["choices"][0]
        message = choice["message"]
        delta = {}
        if message.get("tool_calls"):
            delta["tool_calls"] = []
            for index, item in enumerate(message["tool_calls"]):
                streamed = dict(item)
                streamed["index"] = index
                delta["tool_calls"].append(streamed)
        else:
            delta["content"] = message.get("content") or ""
        event = {
            "choices": [
                {
                    "delta": delta,
                    "finish_reason": choice.get("finish_reason"),
                }
            ]
        }
        body = (
            "data: "
            + json.dumps(event, separators=(",", ":"))
            + "\n\ndata: [DONE]\n\n"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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


def _read_json(path: Path, label: str) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RuntimeError("invalid_%s" % label)
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_%s" % label)
    return payload


def _bundle_runtime_source(bundle_root: Path) -> str:
    expected = os.path.realpath(str(bundle_root / "runtime" / "python" / "python.exe"))
    actual = os.path.realpath(sys.executable)
    if os.path.normcase(actual) != os.path.normcase(expected):
        raise RuntimeError("python_runtime_outside_bundle")
    return "bundle"


def _bundle_identity(bundle_root: Path) -> Tuple[str, str]:
    plan = _read_json(bundle_root / "manifests" / "bundle-plan.json", "bundle_plan")
    flavor_id = str(plan.get("flavor_id") or "").strip()
    application_ids = plan.get("allowed_agent_application_ids")
    shell_ids = plan.get("shell_ids")
    if not flavor_id or not isinstance(application_ids, list) or not application_ids:
        raise RuntimeError("invalid_bundle_plan")
    if not isinstance(shell_ids, list) or "cli" not in shell_ids:
        raise RuntimeError("cli_not_in_bundle_plan")
    application_id = str(application_ids[0] or "").strip()
    if not application_id:
        raise RuntimeError("invalid_bundle_plan")
    return flavor_id, application_id


def _isolated_environment(bundle_root: Path, home: Path) -> Dict[str, str]:
    environment = dict(os.environ)
    for name in tuple(environment):
        if name.startswith("EMBEDAGENT_") or name in (
            "OPENAI_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "PYTHONHOME",
            "PYTHONPATH",
        ):
            environment.pop(name, None)
    environment["EMBEDAGENT_BUNDLE_ROOT"] = str(bundle_root)
    environment["EMBEDAGENT_HOME"] = str(home / ".embedagent")
    environment["HOME"] = str(home)
    environment["USERPROFILE"] = str(home)
    environment["APPDATA"] = str(home / "AppData" / "Roaming")
    drive, tail = os.path.splitdrive(str(home))
    if drive:
        environment["HOMEDRIVE"] = drive
        environment["HOMEPATH"] = tail
    return environment


def _invoke_cli(
    bundle_root: Path,
    arguments: List[str],
    environment: Dict[str, str],
    input_text: str = "",
) -> subprocess.CompletedProcess:
    launcher = bundle_root / "embedagent.cmd"
    if not launcher.is_file():
        raise RuntimeError("cli_launcher_missing")
    comspec = environment.get("COMSPEC") or os.environ.get("COMSPEC") or "cmd.exe"
    command_line = subprocess.list2cmdline([comspec, "/d", "/c"])
    command_line += " call " + subprocess.list2cmdline(
        [str(launcher)] + list(arguments)
    )
    return subprocess.run(
        command_line,
        cwd=str(bundle_root),
        env=environment,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )


def _require_exit(result: subprocess.CompletedProcess, expected: int, scenario: str) -> None:
    if result.returncode != expected:
        categories = re.findall(r"error:\s*([a-z_]+)", result.stderr)
        category = categories[-1] if categories else "unknown"
        raise RuntimeError("%s_exit_%s_%s" % (scenario, result.returncode, category))


def _cli_json(result: subprocess.CompletedProcess, scenario: str) -> Any:
    lines = result.stdout.splitlines()
    if len(lines) != 1:
        candidates = [line for line in lines if line.lstrip().startswith(("{", "["))]
        if "usage:" in result.stderr:
            if "unrecognized arguments" in result.stderr:
                stderr_kind = "usage_extra"
            elif "the following arguments are required" in result.stderr:
                stderr_kind = "usage_missing"
            else:
                stderr_kind = "usage"
        elif "error: interaction_required" in result.stderr:
            stderr_kind = "interaction"
        else:
            stderr_kind = "other"
        raise RuntimeError(
            "%s_stdout_%s_%s_%s"
            % (scenario, len(lines), len(candidates), stderr_kind)
        )
    try:
        return json.loads(lines[0])
    except ValueError:
        raise RuntimeError("%s_json" % scenario)


def _run_arguments(workspace: Path) -> List[str]:
    return [
        "--workspace",
        str(workspace),
        "--max-turns",
        "4",
    ]


def _run_smoke(bundle_root: Path, workspace: Path, home: Path) -> Dict[str, object]:
    runtime_source = _bundle_runtime_source(bundle_root)
    flavor_id, application_id = _bundle_identity(bundle_root)
    launcher = bundle_root / "embedagent.cmd"
    if not launcher.is_file():
        raise RuntimeError("cli_launcher_missing")

    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenAIHandler)
    server_thread = threading.Thread(target=server.serve_forever, name="cli-smoke-model")
    server_thread.daemon = True
    server_thread.start()
    scenarios = dict((scenario_id, False) for scenario_id in _SCENARIO_IDS)
    try:
        port = int(server.server_address[1])
        _write_json(
            home / ".embedagent" / "config.json",
            {
                "base_url": "http://127.0.0.1:%d/v1" % port,
                "model": "cli-smoke-model",
                "timeout": 5,
            },
        )
        _write_json(
            workspace / ".embedagent" / "config.json",
            {
                "allow_system_tool_fallback": False,
                "default_mode": "build",
            },
        )
        environment = _isolated_environment(bundle_root, home)
        common = _run_arguments(workspace)

        run_result = _invoke_cli(
            bundle_root,
            ["run"] + common + ["--output", "json", "smoke"],
            environment,
        )
        _require_exit(run_result, 0, "run_json")
        run_payload = _cli_json(run_result, "run_json")
        if (
            not isinstance(run_payload, dict)
            or run_payload.get("status") != "completed"
            or run_payload.get("final_text") != "CLI smoke completed."
        ):
            raise RuntimeError("run_json_contract")
        session_id = str(run_payload.get("session_id") or "")
        if not session_id:
            raise RuntimeError("run_json_session")
        scenarios["run_json"] = True

        chat_result = _invoke_cli(
            bundle_root,
            ["chat"] + common,
            environment,
            input_text="tool smoke\n/exit\n",
        )
        _require_exit(chat_result, 0, "chat_completion")
        if (
            "CLI smoke completed." not in chat_result.stdout
            or "tool: read_file ok" not in chat_result.stderr
        ):
            raise RuntimeError("chat_completion_contract")
        scenarios["chat_completion"] = True

        permission_result = _invoke_cli(
            bundle_root,
            ["chat"] + common,
            environment,
            input_text="permission smoke\n1\n/exit\n",
        )
        _require_exit(permission_result, 0, "chat_permission")
        if (
            "CLI smoke completed." not in permission_result.stdout
            or not (workspace / "permission-smoke.txt").is_file()
        ):
            raise RuntimeError("chat_permission_contract")
        scenarios["chat_permission"] = True

        input_result = _invoke_cli(
            bundle_root,
            ["chat"] + common,
            environment,
            input_text="ask smoke\n1\n/exit\n",
        )
        _require_exit(input_result, 0, "chat_user_input")
        if "CLI smoke completed." not in input_result.stdout:
            raise RuntimeError("chat_user_input_contract")
        scenarios["chat_user_input"] = True

        list_result = _invoke_cli(
            bundle_root,
            ["sessions", "list"] + common + ["--output", "json"],
            environment,
        )
        _require_exit(list_result, 0, "sessions_list")
        listed = _cli_json(list_result, "sessions_list")
        if not isinstance(listed, list) or session_id not in [
            str(item.get("id") or "") for item in listed if isinstance(item, dict)
        ]:
            raise RuntimeError("sessions_list_contract")
        scenarios["sessions_list"] = True

        show_result = _invoke_cli(
            bundle_root,
            ["sessions", "show"] + common + ["--output", "json", session_id],
            environment,
        )
        _require_exit(show_result, 0, "sessions_show")
        shown = _cli_json(show_result, "sessions_show")
        if not isinstance(shown, dict) or str(shown.get("session_id") or "") != session_id:
            raise RuntimeError("sessions_show_contract")
        scenarios["sessions_show"] = True

        resume_result = _invoke_cli(
            bundle_root,
            ["run"]
            + common
            + ["--resume", session_id, "--output", "json", "smoke"],
            environment,
        )
        _require_exit(resume_result, 0, "run_resume")
        resumed = _cli_json(resume_result, "run_resume")
        if not isinstance(resumed, dict) or resumed.get("session_id") != session_id:
            raise RuntimeError("run_resume_contract")
        scenarios["run_resume"] = True

        blocked_permission = _invoke_cli(
            bundle_root,
            ["run"] + common + ["--output", "json", "permission smoke"],
            environment,
        )
        _require_exit(blocked_permission, 2, "blocked_permission")
        permission_payload = _cli_json(blocked_permission, "blocked_permission")
        if (
            not isinstance(permission_payload, dict)
            or permission_payload.get("status") != "blocked"
            or (permission_payload.get("failure") or {}).get("code")
            != "interaction_required"
        ):
            raise RuntimeError("blocked_permission_contract")
        scenarios["blocked_permission"] = True

        blocked_input = _invoke_cli(
            bundle_root,
            ["run"] + common + ["--output", "json", "ask smoke"],
            environment,
        )
        _require_exit(blocked_input, 2, "blocked_user_input")
        input_payload = _cli_json(blocked_input, "blocked_user_input")
        if (
            not isinstance(input_payload, dict)
            or input_payload.get("status") != "blocked"
            or (input_payload.get("failure") or {}).get("code") != "interaction_required"
        ):
            raise RuntimeError("blocked_user_input_contract")
        scenarios["blocked_user_input"] = True

        return {
            "agent_application_id": application_id,
            "command_launcher": "embedagent.cmd",
            "flavor_id": flavor_id,
            "ok": all(scenarios.values()),
            "runtime_source": runtime_source,
            "scenarios": scenarios,
            "schema_version": 2,
            "system_tool_fallback_allowed": False,
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
    owned_root = ""
    stage = "initialize"
    try:
        workspace_parent = os.path.realpath(args.workspace) if args.workspace else None
        if workspace_parent:
            os.makedirs(workspace_parent, exist_ok=True)
        owned_root = tempfile.mkdtemp(prefix="embedagent-cli-smoke-", dir=workspace_parent)
        state_root = Path(owned_root)
        workspace = state_root / "workspace"
        home = state_root / "home"
        workspace.mkdir(parents=True)
        home.mkdir(parents=True)
        (workspace / "README.md").write_text("CLI smoke workspace\n", encoding="ascii")
        stage = "launcher"
        payload = _run_smoke(bundle_root, workspace, home)
        _write_json(report_path, payload)
        print("CLI smoke validation passed.")
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        failure_code = str(exc) if type(exc) is RuntimeError else type(exc).__name__
        _write_json(
            report_path,
            {
                "error_type": type(exc).__name__,
                "failure_code": failure_code,
                "failure_stage": stage,
                "ok": False,
                "schema_version": 2,
            },
        )
        print("CLI smoke validation failed at %s (%s)." % (stage, type(exc).__name__))
        return 1
    finally:
        if owned_root:
            shutil.rmtree(owned_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
