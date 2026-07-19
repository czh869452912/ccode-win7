#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional

import websockets

REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_EXE = os.path.join(REPO_ROOT, ".venv", "Scripts", "python.exe")
FIXED_WEBVIEW2_RELATIVE_EXE = r"runtime\webview2-fixed-runtime\msedgewebview2.exe"
EXPECTED_WEBVIEW2_FIXED_RUNTIME_MAJOR = 109


class SmokeFailure(RuntimeError):
    def __init__(self, category: str, stage: str, details: Dict[str, object]):
        self.category = str(category)
        self.stage = str(stage)
        self.details = dict(details or {})
        super().__init__(self.details.get("message") or self.category)

_FAILURE_CATEGORIES = (
    "launcher_exit",
    "http_timeout",
    "app_bootstrap_failure",
    "protocol_failure",
    "model_failure",
    "renderer_failure",
    "cleanup_failure",
)

_SENSITIVE_KEYS = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "credential",
    "prompt",
    "raw_output",
)


def _safe_details(value):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if any(part in str(key).lower() for part in _SENSITIVE_KEYS):
                continue
            result[str(key)] = _safe_details(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_details(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _tail_text(path, max_lines=40):
    if not path or not os.path.isfile(str(path)):
        return []
    try:
        with open(str(path), "r", encoding="utf-8", errors="replace") as handle:
            lines = [line.rstrip("\r\n") for line in handle.readlines()]
        return lines[-int(max_lines) :]
    except (OSError, ValueError):
        return []


def _process_exit_details(process):
    if process is None:
        return None
    return getattr(process, "returncode", None)


def _failure_payload(failure, process, stdout_path, stderr_path, checks):
    return {
        "ok": False,
        "failure": {
            "category": failure.category,
            "stage": failure.stage,
            "details": _safe_details(failure.details),
        },
        "process": {
            "pid": getattr(process, "pid", None) if process is not None else None,
            "returncode": _process_exit_details(process),
        },
        "stdout_path": str(stdout_path or ""),
        "stderr_path": str(stderr_path or ""),
        "stdout_tail": _tail_text(stdout_path),
        "stderr_tail": _tail_text(stderr_path),
        "checks": list(checks or []),
    }


def _write_json_report(path, payload):
    if not path:
        return
    report_path = os.path.realpath(str(path))
    parent = os.path.dirname(report_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    temp_path = report_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, report_path)


def _emit_report(payload, report_path):
    _write_json_report(report_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class FakeOpenAIHandler(BaseHTTPRequestHandler):
    assistant_text = "GUI smoke reply"
    requests_seen = []  # type: List[Dict[str, object]]

    def log_message(self, format, *args):  # noqa: A003
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        FakeOpenAIHandler.requests_seen.append(payload)
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        messages = payload.get("messages") or []
        user_text = self._last_user_message(messages)
        has_tool_result = self._has_tool_result_after_last_user(messages)
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            for item in self._stream_chunks(user_text, has_tool_result):
                data = ("data: %s\n\n" % json.dumps(item)).encode("utf-8")
                self.wfile.write(data)
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        body = self._completion_payload(user_text, has_tool_result)
        encoded = json.dumps(body).encode("utf-8")
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
        saw_user = False
        for item in reversed(messages):
            if item.get("role") == "tool":
                saw_user = True
            elif item.get("role") == "user":
                return saw_user
        return False

    def _stream_chunks(self, user_text, has_tool_result):
        if not has_tool_result:
            tool_call = self._tool_call_for_text(user_text)
            if tool_call is not None:
                return [
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": tool_call["id"],
                                            "function": {
                                                "name": tool_call["name"],
                                                "arguments": json.dumps(
                                                    tool_call["arguments"], ensure_ascii=False
                                                ),
                                            },
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "delta": {},
                                "finish_reason": "tool_calls",
                            }
                        ]
                    },
                ]
        final_text = self._final_text(user_text)
        return [
            {
                "choices": [
                    {
                        "delta": {"content": final_text},
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ]
            },
        ]

    def _completion_payload(self, user_text, has_tool_result):
        if not has_tool_result:
            tool_call = self._tool_call_for_text(user_text)
            if tool_call is not None:
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": tool_call["id"],
                                        "type": "function",
                                        "function": {
                                            "name": tool_call["name"],
                                            "arguments": json.dumps(
                                                tool_call["arguments"], ensure_ascii=False
                                            ),
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
        return {
            "choices": [
                {
                    "message": {"content": self._final_text(user_text)},
                    "finish_reason": "stop",
                }
            ]
        }

    @staticmethod
    def _tool_call_for_text(user_text):
        text = (user_text or "").lower()
        if "permission" in text:
            return {
                "id": "call-permission",
                "name": "run_command",
                "arguments": {"command": "echo gui smoke permission", "cwd": ".", "timeout_sec": 5},
            }
        if "ask" in text:
            return {
                "id": "call-ask",
                "name": "ask_user",
                "arguments": {
                    "question": "继续哪一步？",
                    "option_1": "继续当前方案",
                    "option_2": "切到 debug 模式",
                    "option_2_mode": "debug",
                },
            }
        if "task" in text:
            return {
                "id": "call-task",
                "name": "task_status",
                "arguments": {},
            }
        if "tool" in text:
            return {
                "id": "call-readme",
                "name": "read_file",
                "arguments": {"path": "README.md"},
            }
        return None

    def _final_text(self, user_text):
        text = (user_text or "").lower()
        if "permission" in text:
            return "permission flow ok"
        if "ask" in text:
            return "ask flow ok"
        if "task" in text:
            return "task flow ok"
        return self.assistant_text




def _wait_for_http(
    url: str,
    timeout: float,
    process=None,
    stage: str = "http",
    checks=None,
) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        exit_code = _process_exit_details(process)
        if exit_code is not None:
            raise SmokeFailure(
                "launcher_exit",
                stage,
                {"returncode": int(exit_code), "url": url},
            )
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.status == 200:
                    if checks is not None:
                        checks.append(stage)
                    return
        except Exception as exc:  # pragma: no cover - smoke helper
            last_error = exc
        time.sleep(0.25)
    raise SmokeFailure(
        "http_timeout",
        stage,
        {"url": url, "timeout_sec": timeout, "last_error": str(last_error or "")},
    )


def _wait_for_app_bootstrap(gui_port, timeout, process, checks):
    url = "http://127.0.0.1:%d/api/app/bootstrap" % gui_port
    try:
        _wait_for_http(url, timeout, process=process, stage="app_bootstrap", checks=checks)
        _json_request(url)
    except SmokeFailure:
        raise
    except Exception as exc:
        raise SmokeFailure(
            "app_bootstrap_failure",
            "app_bootstrap",
            {"url": url, "message": str(exc)},
        )
def _json_request(
    url: str, method: str = "GET", payload: Dict[str, object] = None
) -> Dict[str, object]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10.0) as response:
        return json.loads(response.read().decode("utf-8"))


async def _consume_until_idle(websocket, session_id: str, summary: Dict[str, object]) -> None:
    saw_running = False
    saw_command_result = False
    deadline = time.time() + 20.0
    while time.time() < deadline:
        remaining = max(0.1, deadline - time.time())
        raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
        payload = json.loads(raw)
        msg_type = payload.get("type")
        data = payload.get("data") or {}
        snapshot = (
            data.get("session_snapshot") if isinstance(data.get("session_snapshot"), dict) else {}
        )
        target_session = str(snapshot.get("session_id") or data.get("session_id") or "")
        if target_session and target_session != session_id:
            continue
        if msg_type == "stream_delta":
            summary["stream_deltas"].append(str(data.get("text") or ""))
        elif msg_type == "tool_start":
            summary["tool_events"].append(
                {
                    "type": "tool_start",
                    "call_id": data.get("call_id"),
                    "tool_name": data.get("tool_name"),
                }
            )
        elif msg_type == "tool_finish":
            summary["tool_events"].append(
                {
                    "type": "tool_finish",
                    "call_id": data.get("call_id"),
                    "tool_name": data.get("tool_name"),
                }
            )
        elif msg_type == "command_result":
            saw_command_result = True
            summary["command_results"].append(
                {
                    "command_name": data.get("command_name"),
                    "success": bool(data.get("success")),
                    "message": data.get("message") or "",
                    "data": data.get("data") or {},
                }
            )
            if not saw_running:
                return
        elif msg_type == "permission_request":
            summary["permission_requests"] += 1
            await websocket.send(
                json.dumps(
                    {
                        "type": "permission_response",
                        "permission_id": data.get("permission_id"),
                        "approved": True,
                    }
                )
            )
        elif msg_type == "user_input_request":
            summary["user_input_requests"] += 1
            options = data.get("options") or []
            selected = options[1] if len(options) > 1 else (options[0] if options else {})
            await websocket.send(
                json.dumps(
                    {
                        "type": "user_input_response",
                        "request_id": data.get("request_id"),
                        "answer": selected.get("text") or "继续当前方案",
                        "selected_index": selected.get("index"),
                        "selected_mode": selected.get("mode") or "",
                        "selected_option_text": selected.get("text") or "",
                    }
                )
            )
        elif msg_type == "session_status":
            status = str(data.get("status") or snapshot.get("status") or "")
            summary["session_statuses"].append(status)
            if status == "running":
                saw_running = True
            if saw_running and status == "idle":
                return
            if saw_command_result and status == "idle":
                return
    raise RuntimeError("Timed out waiting for session to return to idle")


async def _exercise_gui(gui_port: int) -> Dict[str, object]:
    websocket_url = "ws://127.0.0.1:%d/ws" % gui_port
    api_root = "http://127.0.0.1:%d" % gui_port
    summary = {
        "stream_deltas": [],
        "session_statuses": [],
        "tool_events": [],
        "command_results": [],
        "permission_requests": 0,
        "user_input_requests": 0,
    }
    async with websockets.connect(websocket_url) as websocket:
        session = _json_request(api_root + "/api/sessions?mode=build", method="POST")
        session_id = str(session.get("session_id") or "")
        if not session_id:
            raise RuntimeError("GUI session creation returned no session_id")
        _json_request(
            api_root + "/api/sessions/%s/message" % session_id,
            method="POST",
            payload={"text": "tool smoke"},
        )
        await _consume_until_idle(websocket, session_id, summary)

        _json_request(
            api_root + "/api/sessions/%s/message" % session_id,
            method="POST",
            payload={"text": "task smoke"},
        )
        await _consume_until_idle(websocket, session_id, summary)

        _json_request(
            api_root + "/api/sessions/%s/message" % session_id,
            method="POST",
            payload={"text": "ask smoke"},
        )
        await _consume_until_idle(websocket, session_id, summary)

        _json_request(
            api_root + "/api/sessions/%s/message" % session_id,
            method="POST",
            payload={"text": "permission smoke"},
        )
        await _consume_until_idle(websocket, session_id, summary)

        _json_request(
            api_root + "/api/sessions/%s/message" % session_id,
            method="POST",
            payload={"text": "/review"},
        )
        await _consume_until_idle(websocket, session_id, summary)

        first_bootstrap = _json_request(api_root + "/api/sessions/%s/bootstrap" % session_id)
        second_session = _json_request(api_root + "/api/sessions?mode=build", method="POST")
        second_session_id = str(second_session.get("session_id") or "")
        second_bootstrap = _json_request(
            api_root + "/api/sessions/%s/bootstrap" % second_session_id
        )

        summary["session_id"] = session_id
        summary["assistant_text"] = "".join(summary["stream_deltas"])
        summary["first_session_task_items"] = len(
            (first_bootstrap.get("snapshot") or {}).get("task_items") or []
        )
        summary["second_session_task_items"] = len(
            (second_bootstrap.get("snapshot") or {}).get("task_items") or []
        )
        summary["second_session_id"] = second_session_id
        return summary


def _build_command(
    bundle_root: Optional[str], workspace_dir: str, model_port: int, gui_port: int
) -> Dict[str, object]:
    if bundle_root:
        native_launcher = os.path.join(bundle_root, "embedagent-gui.exe")
        cmd_launcher = os.path.join(bundle_root, "embedagent-gui.cmd")
        launcher = native_launcher if os.path.isfile(native_launcher) else cmd_launcher
        if not os.path.isfile(launcher):
            raise RuntimeError(
                "GUI launcher not found in bundle: %s or %s" % (native_launcher, cmd_launcher)
            )
        return {
            "command": [
                launcher,
                "--workspace",
                workspace_dir,
                "--model",
                "gui-smoke-model",
                "--base-url",
                "http://127.0.0.1:%d/v1" % model_port,
                "--port",
                str(gui_port),
                "--timeout",
                "20",
                "--max-turns",
                "2",
            ],
            "cwd": bundle_root,
            "env": dict(os.environ),
        }

    if not os.path.isfile(PYTHON_EXE):
        raise RuntimeError("Python venv not found: %s" % PYTHON_EXE)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(REPO_ROOT, "src")
    return {
        "command": [
            PYTHON_EXE,
            "-m",
            "embedagent.frontend.gui.launcher",
            "--workspace",
            workspace_dir,
            "--model",
            "gui-smoke-model",
            "--base-url",
            "http://127.0.0.1:%d/v1" % model_port,
            "--port",
            str(gui_port),
            "--timeout",
            "20",
            "--max-turns",
            "2",
        ],
        "cwd": REPO_ROOT,
        "env": env,
    }


def _detect_webview2_runtime_major(runtime_path: str) -> Optional[int]:
    parts = os.path.normpath(runtime_path or "").split(os.sep)
    for item in reversed(parts):
        first = item.split(".", 1)[0]
        if first.isdigit():
            return int(first)
    return None


def _fixed_webview2_report(bundle_root: str) -> Dict[str, object]:
    runtime_exe = os.path.join(bundle_root, *FIXED_WEBVIEW2_RELATIVE_EXE.split("\\"))
    runtime_path = os.path.dirname(runtime_exe)
    return {
        "required": True,
        "expected_runtime_major": EXPECTED_WEBVIEW2_FIXED_RUNTIME_MAJOR,
        "runtime_exe": runtime_exe,
        "runtime_path": runtime_path,
        "runtime_major": _detect_webview2_runtime_major(runtime_path),
        "exists": os.path.isfile(runtime_exe),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate GUI smoke flow.")
    parser.add_argument(
        "--bundle-root",
        default="",
        help="Optional offline bundle root to launch instead of source tree",
    )
    parser.add_argument(
        "--workspace", default="", help="Optional workspace path to use during smoke validation"
    )
    parser.add_argument(
        "--windowed", action="store_true", help="Launch a real GUI window and auto-close it"
    )
    parser.add_argument(
        "--auto-close-seconds", type=float, default=8.0, help="Auto-close delay for windowed smoke"
    )
    parser.add_argument(
        "--require-fixed-webview2",
        action="store_true",
        help="Require bundled Fixed Version WebView2 109 when validating a bundle.",
    )
    parser.add_argument("--json-report", default="", help="Write a structured smoke report")
    parser.add_argument(
        "--diagnostic-dir", default="", help="Directory for launcher stdout/stderr"
    )
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    return parser


def _legacy_main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    bundle_root = os.path.realpath(args.bundle_root) if args.bundle_root else ""
    fixed_webview2 = {}
    if args.require_fixed_webview2:
        if not bundle_root:
            raise RuntimeError("--require-fixed-webview2 requires --bundle-root")
        fixed_webview2 = _fixed_webview2_report(bundle_root)
        if not fixed_webview2.get("exists"):
            raise RuntimeError(
                "Bundled Fixed Version WebView2 runtime is missing: %s"
                % fixed_webview2.get("runtime_exe")
            )

    model_port = _free_port()
    gui_port = _free_port()
    model_server = ThreadingHTTPServer(("127.0.0.1", model_port), FakeOpenAIHandler)
    server_thread = threading.Thread(target=model_server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    process = None
    workspace_dir = (
        os.path.realpath(args.workspace)
        if args.workspace
        else tempfile.mkdtemp(prefix="embedagent-gui-smoke-")
    )
    if not os.path.isdir(workspace_dir):
        os.makedirs(workspace_dir)
    try:
        launch = _build_command(bundle_root or None, workspace_dir, model_port, gui_port)
        renderer_report_path = os.path.join(workspace_dir, "renderer-report.json")
        launch["command"] += ["--renderer-report", renderer_report_path]
        if args.windowed:
            launch["command"] += ["--auto-close-seconds", str(args.auto_close_seconds)]
        else:
            launch["command"].append("--headless")
        process = subprocess.Popen(
            launch["command"],
            cwd=str(launch["cwd"]),
            env=launch["env"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_http("http://127.0.0.1:%d/" % gui_port, timeout=20.0)
        summary = asyncio.run(_exercise_gui(gui_port))
        if "GUI smoke reply" not in summary.get("assistant_text", ""):
            raise RuntimeError("GUI smoke did not receive assistant stream text: %s" % summary)
        if not FakeOpenAIHandler.requests_seen:
            raise RuntimeError("Fake model server did not receive any request")
        if summary.get("permission_requests", 0) < 1 or summary.get("user_input_requests", 0) < 1:
            raise RuntimeError(
                "GUI smoke did not exercise permission/user-input flows: %s" % summary
            )
        tool_event_types = [item.get("type") for item in summary.get("tool_events", [])]
        if "tool_start" not in tool_event_types or "tool_finish" not in tool_event_types:
            raise RuntimeError("GUI smoke did not exercise tool events: %s" % summary)
        review_commands = [
            item
            for item in summary.get("command_results", [])
            if item.get("command_name") == "review"
        ]
        if not review_commands or not review_commands[0].get("success"):
            raise RuntimeError("GUI smoke did not exercise /review workflow: %s" % summary)
        if (
            "first_session_task_items" not in summary
            or "second_session_task_items" not in summary
        ):
            raise RuntimeError("GUI smoke bootstrap task projection check failed: %s" % summary)
        renderer_report = {}
        if os.path.isfile(renderer_report_path):
            with open(renderer_report_path, "r", encoding="utf-8") as handle:
                renderer_report = json.load(handle)
        if bundle_root and renderer_report.get("runtime_source") != "bundle":
            raise RuntimeError(
                "Bundle GUI did not use bundled Chromium runtime: %s" % renderer_report
            )
        if args.require_fixed_webview2:
            if renderer_report.get("renderer") != "edgechromium":
                raise RuntimeError(
                    "Bundle GUI did not use edgechromium renderer: %s" % renderer_report
                )
            if renderer_report.get("runtime_source") != "bundle":
                raise RuntimeError(
                    "Bundle GUI did not use bundled WebView2 runtime: %s" % renderer_report
                )
        print(
            json.dumps(
                {
                    "bundle_root": bundle_root or "",
                    "workspace": workspace_dir,
                    "gui_port": gui_port,
                    "model_port": model_port,
                    "assistant_text": summary.get("assistant_text"),
                    "session_statuses": summary.get("session_statuses"),
                    "tool_events": summary.get("tool_events"),
                    "command_results": summary.get("command_results"),
                    "model_requests": len(FakeOpenAIHandler.requests_seen),
                    "renderer_report": renderer_report,
                    "fixed_webview2": fixed_webview2,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        model_server.shutdown()
        model_server.server_close()
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                process.wait(timeout=10.0)



def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    bundle_root = os.path.realpath(args.bundle_root) if args.bundle_root else ""
    workspace_dir = (
        os.path.realpath(args.workspace)
        if args.workspace
        else tempfile.mkdtemp(prefix="embedagent-gui-smoke-")
    )
    if not os.path.isdir(workspace_dir):
        os.makedirs(workspace_dir)
    diagnostic_dir = os.path.realpath(args.diagnostic_dir or os.path.join(workspace_dir, "diagnostics"))
    if not os.path.isdir(diagnostic_dir):
        os.makedirs(diagnostic_dir)
    stdout_path = os.path.join(diagnostic_dir, "launcher.stdout.log")
    stderr_path = os.path.join(diagnostic_dir, "launcher.stderr.log")
    stdout_handle = None
    stderr_handle = None
    process = None
    checks = []
    fixed_webview2 = {}
    model_server = None
    try:
        if args.require_fixed_webview2:
            if not bundle_root:
                raise SmokeFailure(
                    "renderer_failure",
                    "fixed_webview2",
                    {"message": "--require-fixed-webview2 requires --bundle-root"},
                )
            fixed_webview2 = _fixed_webview2_report(bundle_root)
            if not fixed_webview2.get("exists"):
                raise SmokeFailure(
                    "renderer_failure",
                    "fixed_webview2",
                    {"runtime_exe": fixed_webview2.get("runtime_exe")},
                )

        FakeOpenAIHandler.requests_seen = []
        model_port = _free_port()
        gui_port = _free_port()
        model_server = ThreadingHTTPServer(("127.0.0.1", model_port), FakeOpenAIHandler)
        server_thread = threading.Thread(target=model_server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        launch = _build_command(bundle_root or None, workspace_dir, model_port, gui_port)
        renderer_report_path = os.path.join(workspace_dir, "renderer-report.json")
        launch["command"] += ["--renderer-report", renderer_report_path]
        startup_report_path = os.path.join(diagnostic_dir, "startup-report.json")
        launch["command"] += ["--startup-report", startup_report_path]
        if args.windowed:
            launch["command"] += ["--auto-close-seconds", str(args.auto_close_seconds)]
        else:
            launch["command"].append("--headless")
        stdout_handle = open(stdout_path, "w", encoding="utf-8")
        stderr_handle = open(stderr_path, "w", encoding="utf-8")
        process = subprocess.Popen(
            launch["command"],
            cwd=str(launch["cwd"]),
            env=launch["env"],
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
        _wait_for_http(
            "http://127.0.0.1:%d/" % gui_port,
            timeout=args.startup_timeout,
            process=process,
            stage="http",
            checks=checks,
        )
        _wait_for_app_bootstrap(gui_port, args.startup_timeout, process, checks)
        try:
            summary = asyncio.run(_exercise_gui(gui_port))
        except SmokeFailure:
            raise
        except Exception as exc:
            raise SmokeFailure(
                "protocol_failure",
                "exercise",
                {"message": "%s: %s" % (type(exc).__name__, str(exc))},
            )
        checks.append("exercise")
        if "GUI smoke reply" not in summary.get("assistant_text", ""):
            raise SmokeFailure(
                "model_failure",
                "assistant_stream",
                {"message": "GUI smoke did not receive assistant stream text"},
            )
        if not FakeOpenAIHandler.requests_seen:
            raise SmokeFailure(
                "model_failure", "model_request", {"message": "fake model received no request"}
            )
        if summary.get("permission_requests", 0) < 1 or summary.get("user_input_requests", 0) < 1:
            raise SmokeFailure(
                "protocol_failure",
                "interaction",
                {"message": "permission/user-input flow was not exercised"},
            )
        tool_event_types = [item.get("type") for item in summary.get("tool_events", [])]
        if "tool_start" not in tool_event_types or "tool_finish" not in tool_event_types:
            raise SmokeFailure(
                "protocol_failure", "tool_events", {"message": "tool events were not exercised"}
            )
        review_commands = [
            item
            for item in summary.get("command_results", [])
            if item.get("command_name") == "review"
        ]
        if not review_commands or not review_commands[0].get("success"):
            raise SmokeFailure(
                "protocol_failure", "review", {"message": "/review workflow failed"}
            )
        if "first_session_task_items" not in summary or "second_session_task_items" not in summary:
            raise SmokeFailure(
                "protocol_failure", "task_projection", {"message": "task projection check failed"}
            )
        renderer_report = {}
        if os.path.isfile(renderer_report_path):
            with open(renderer_report_path, "r", encoding="utf-8") as handle:
                renderer_report = json.load(handle)
        if bundle_root and renderer_report.get("runtime_source") != "bundle":
            raise SmokeFailure(
                "renderer_failure",
                "renderer_report",
                {"message": "bundle GUI did not use bundled Chromium runtime"},
            )
        if args.require_fixed_webview2:
            if renderer_report.get("renderer") != "edgechromium":
                raise SmokeFailure(
                    "renderer_failure",
                    "renderer_report",
                    {"message": "bundle GUI did not use edgechromium renderer"},
                )
            if renderer_report.get("runtime_source") != "bundle":
                raise SmokeFailure(
                    "renderer_failure",
                    "renderer_report",
                    {"message": "bundle GUI did not use bundled WebView2 runtime"},
                )
        payload = {
            "ok": True,
            "bundle_root": bundle_root or "",
            "workspace": workspace_dir,
            "diagnostic_dir": diagnostic_dir,
            "gui_port": gui_port,
            "model_port": model_port,
            "assistant_text": summary.get("assistant_text"),
            "session_statuses": summary.get("session_statuses"),
            "tool_events": summary.get("tool_events"),
            "command_results": summary.get("command_results"),
            "model_requests": len(FakeOpenAIHandler.requests_seen),
            "renderer_report": renderer_report,
            "fixed_webview2": fixed_webview2,
            "checks": checks,
        }
        _emit_report(payload, args.json_report)
        return 0
    except SmokeFailure as failure:
        if stdout_handle:
            stdout_handle.flush()
        if stderr_handle:
            stderr_handle.flush()
        _emit_report(
            _failure_payload(failure, process, stdout_path, stderr_path, checks),
            args.json_report,
        )
        return 1
    except Exception as exc:
        if stdout_handle:
            stdout_handle.flush()
        if stderr_handle:
            stderr_handle.flush()
        failure = SmokeFailure("protocol_failure", "startup", {"message": str(exc)})
        _emit_report(
            _failure_payload(failure, process, stdout_path, stderr_path, checks),
            args.json_report,
        )
        return 1
    finally:
        if model_server is not None:
            model_server.shutdown()
            model_server.server_close()
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                process.wait(timeout=10.0)
        if stdout_handle:
            stdout_handle.close()
        if stderr_handle:
            stderr_handle.close()
if __name__ == "__main__":
    sys.exit(main())
