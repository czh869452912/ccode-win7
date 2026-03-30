#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import argparse
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
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            chunks = [
                {
                    "choices": [
                        {
                            "delta": {"content": self.assistant_text},
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
            for item in chunks:
                data = ("data: %s\n\n" % json.dumps(item)).encode("utf-8")
                self.wfile.write(data)
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        body = {
            "choices": [
                {
                    "message": {"content": self.assistant_text},
                    "finish_reason": "stop",
                }
            ]
        }
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _wait_for_http(url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # pragma: no cover - smoke helper
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError("Timed out waiting for %s: %s" % (url, last_error))


def _json_request(url: str, method: str = "GET", payload: Dict[str, object] = None) -> Dict[str, object]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10.0) as response:
        return json.loads(response.read().decode("utf-8"))


async def _exercise_gui(gui_port: int) -> Dict[str, object]:
    websocket_url = "ws://127.0.0.1:%d/ws" % gui_port
    api_root = "http://127.0.0.1:%d" % gui_port
    summary = {
        "stream_deltas": [],
        "session_statuses": [],
        "tool_events": [],
    }
    async with websockets.connect(websocket_url) as websocket:
        session = _json_request(api_root + "/api/sessions?mode=code", method="POST")
        session_id = str(session.get("session_id") or "")
        if not session_id:
            raise RuntimeError("GUI session creation returned no session_id")

        _json_request(
            api_root + "/api/sessions/%s/message" % session_id,
            method="POST",
            payload={"text": "Say hello from GUI smoke"},
        )

        deadline = time.time() + 20.0
        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            payload = json.loads(raw)
            msg_type = payload.get("type")
            data = payload.get("data") or {}
            if msg_type == "stream_delta":
                summary["stream_deltas"].append(str(data.get("text") or ""))
            elif msg_type == "session_status":
                summary["session_statuses"].append(str(data.get("status") or ""))
                if data.get("status") == "idle" and "".join(summary["stream_deltas"]):
                    break
            elif msg_type in ("tool_start", "tool_finish"):
                summary["tool_events"].append(msg_type)

        summary["session_id"] = session_id
        summary["assistant_text"] = "".join(summary["stream_deltas"])
        return summary


def _build_command(bundle_root: Optional[str], workspace_dir: str, model_port: int, gui_port: int) -> Dict[str, object]:
    if bundle_root:
        launcher = os.path.join(bundle_root, "embedagent-gui.cmd")
        if not os.path.isfile(launcher):
            raise RuntimeError("GUI launcher not found in bundle: %s" % launcher)
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
                "--headless",
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
            "--headless",
            "--timeout",
            "20",
            "--max-turns",
            "2",
        ],
        "cwd": REPO_ROOT,
        "env": env,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate headless GUI smoke flow.")
    parser.add_argument("--bundle-root", default="", help="Optional offline bundle root to launch instead of source tree")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    bundle_root = os.path.realpath(args.bundle_root) if args.bundle_root else ""

    model_port = _free_port()
    gui_port = _free_port()
    model_server = ThreadingHTTPServer(("127.0.0.1", model_port), FakeOpenAIHandler)
    server_thread = threading.Thread(target=model_server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    process = None
    workspace_dir = tempfile.mkdtemp(prefix="embedagent-gui-smoke-")
    try:
        launch = _build_command(bundle_root or None, workspace_dir, model_port, gui_port)
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
        print(json.dumps({
            "bundle_root": bundle_root or "",
            "workspace": workspace_dir,
            "gui_port": gui_port,
            "model_port": model_port,
            "assistant_text": summary.get("assistant_text"),
            "session_statuses": summary.get("session_statuses"),
            "tool_events": summary.get("tool_events"),
            "model_requests": len(FakeOpenAIHandler.requests_seen),
        }, ensure_ascii=False, indent=2))
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


if __name__ == "__main__":
    sys.exit(main())
