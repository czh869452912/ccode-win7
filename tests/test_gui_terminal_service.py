import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.terminal_service import TerminalService


class FakeStdin(object):
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    def flush(self):
        return None

    def close(self):
        self.closed = True


class FakePipe(object):
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def readline(self):
        if self._chunks:
            return self._chunks.pop(0)
        return b""

    def close(self):
        return None


class FakeProcess(object):
    def __init__(self, pid=123, stdout=None, stderr=None):
        self.pid = pid
        self.stdin = FakeStdin()
        self.stdout = FakePipe(stdout or [])
        self.stderr = FakePipe(stderr or [])
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -1


class FakeProcessFactory(object):
    def __init__(self, stdout_sequences=None):
        self.calls = []
        self.processes = []
        self.stdout_sequences = list(stdout_sequences or [[b"hello from terminal\n"]])

    def __call__(self, command, cwd, env):
        stdout = self.stdout_sequences.pop(0) if self.stdout_sequences else []
        process = FakeProcess(stdout=stdout)
        self.calls.append((command, cwd, env))
        self.processes.append(process)
        return process


class TerminalServiceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="embedagent-terminal-")
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        self.events = []

    def service(self, factory=None):
        return TerminalService(
            workspace_root=self.workspace,
            process_factory=factory or FakeProcessFactory(),
            event_sink=self.events.append,
            shell_resolver=lambda: ["cmd.exe"],
            reader_join_timeout=0.2,
        )

    def test_open_or_attach_captures_output_and_returns_snapshot(self):
        factory = FakeProcessFactory()
        service = self.service(factory)

        snapshot = service.open_or_attach("sess-1", "term-1", cwd="", cols=80, rows=24)
        service.wait_for_idle("sess-1", "term-1", timeout=1.0)

        refreshed = service.snapshot("sess-1", "term-1")
        self.assertEqual(snapshot["session_id"], "sess-1")
        self.assertEqual(snapshot["terminal_id"], "term-1")
        self.assertEqual(snapshot["status"], "running")
        self.assertEqual(refreshed["history"], "hello from terminal\n")
        self.assertEqual(refreshed["capabilities"]["pty"], False)
        self.assertEqual(refreshed["capabilities"]["resize"], False)
        self.assertEqual(factory.calls[0][1], os.path.realpath(self.workspace))
        self.assertTrue(any(event["type"] == "output" for event in self.events))

    def test_client_chosen_terminal_ids_are_validated(self):
        service = self.service()

        with self.assertRaises(ValueError) as raised:
            service.open_or_attach("sess-1", "   ")

        self.assertEqual(str(raised.exception), "invalid_terminal_id")

    def test_cwd_must_stay_inside_workspace(self):
        service = self.service()
        outside = os.path.dirname(os.path.realpath(self.workspace))

        with self.assertRaises(ValueError) as raised:
            service.open_or_attach("sess-1", "term-1", cwd=outside)

        self.assertEqual(str(raised.exception), "terminal_cwd_outside_workspace")

    def test_write_clear_resize_close_and_shutdown(self):
        factory = FakeProcessFactory()
        service = self.service(factory)
        service.open_or_attach("sess-1", "term-1")
        service.write("sess-1", "term-1", "echo hi\n")

        self.assertEqual(factory.processes[0].stdin.writes, ["echo hi\n"])

        cleared = service.clear("sess-1", "term-1")
        self.assertEqual(cleared["history"], "")
        resized = service.resize("sess-1", "term-1", cols=120, rows=40)
        self.assertEqual(resized["cols"], 120)
        self.assertEqual(resized["rows"], 40)
        self.assertEqual(resized["capabilities"]["resize"], False)

        closed = service.close("sess-1", "term-1")
        self.assertEqual(closed["status"], "closed")
        self.assertTrue(factory.processes[0].terminated)

        with self.assertRaises(ValueError) as raised:
            service.write("sess-1", "term-1", "again\n")
        self.assertEqual(str(raised.exception), "terminal_not_found")

    def test_restart_reuses_terminal_id_and_resets_history(self):
        factory = FakeProcessFactory(stdout_sequences=[[b"first\n"], []])
        service = self.service(factory)
        service.open_or_attach("sess-1", "term-1")
        service.wait_for_idle("sess-1", "term-1", timeout=1.0)

        restarted = service.restart("sess-1", "term-1", cwd="", cols=90, rows=30)
        service.wait_for_idle("sess-1", "term-1", timeout=1.0)

        self.assertEqual(restarted["terminal_id"], "term-1")
        self.assertEqual(service.snapshot("sess-1", "term-1")["history"], "")
        self.assertEqual(restarted["cols"], 90)
        self.assertEqual(len(factory.processes), 2)


if __name__ == "__main__":
    unittest.main()
