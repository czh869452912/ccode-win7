import multiprocessing
import os
import shutil
import sys
import threading
import unittest
from copy import deepcopy
from itertools import count
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.transcript_store import TranscriptStore
from embedagent_core.session_log import SessionLeaseConflict

_COUNTER = count(1)


def _make_workspace(name):
    root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "build",
        "test-sandboxes",
        "%s-%s-%s" % (name, os.getpid(), next(_COUNTER)),
    )
    root = os.path.realpath(root)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    return root


def _hold_transcript_lease(workspace, ready, release):
    store = TranscriptStore(workspace)
    with store.acquire_lease("session-process"):
        ready.set()
        if not release.wait(10):
            raise RuntimeError("lease release signal was not received")


def _attempt_transcript_lease(workspace, session_id, result):
    store = TranscriptStore(workspace)
    try:
        with store.acquire_lease(session_id):
            result.put("acquired")
    except SessionLeaseConflict:
        result.put("conflict")


class TestTranscriptStore(unittest.TestCase):
    def setUp(self):
        self.workspace = _make_workspace("transcript-store")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    @unittest.skipUnless(os.name == "nt", "Windows workspace handle contract")
    def test_constructor_rejects_missing_workspace_without_creating_it(self):
        missing_workspace = os.path.join(self.workspace, "missing-workspace")

        with self.assertRaisesRegex(ValueError, "^workspace is invalid$"):
            TranscriptStore(missing_workspace)

        self.assertFalse(os.path.exists(missing_workspace))

    def test_same_session_cannot_hold_overlapping_leases(self):
        store = TranscriptStore(self.workspace)

        with store.acquire_lease("session-one"):
            with self.assertRaises(SessionLeaseConflict):
                with store.acquire_lease("session-one"):
                    pass

    def test_different_sessions_can_hold_nested_leases(self):
        store = TranscriptStore(self.workspace)

        with store.acquire_lease("session-one"):
            with store.acquire_lease("session-two"):
                pass

    def test_lease_is_released_after_exception(self):
        store = TranscriptStore(self.workspace)

        with self.assertRaises(RuntimeError):
            with store.acquire_lease("session-one"):
                raise RuntimeError("stop")

        with store.acquire_lease("session-one"):
            pass

    def test_process_lease_is_released_when_mutex_release_raises(self):
        store = TranscriptStore(self.workspace)
        with patch.object(store, "_acquire_windows_mutex", return_value=123):
            with patch.object(
                store,
                "_release_windows_mutex",
                side_effect=RuntimeError("mutex release failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "^mutex release failed$"):
                    with store.acquire_lease("session-release-error"):
                        pass

        with TranscriptStore(self.workspace).acquire_lease("session-release-error"):
            pass

    def test_lease_creates_no_filesystem_artifact_or_session_directory(self):
        store = TranscriptStore(self.workspace)
        transcript_path = store.resolve_transcript_path("session-no-artifact")
        session_dir = os.path.dirname(transcript_path)

        with store.acquire_lease("session-no-artifact"):
            self.assertFalse(os.path.lexists(transcript_path + ".lease"))
            self.assertFalse(os.path.exists(session_dir))

        self.assertFalse(os.path.lexists(transcript_path + ".lease"))
        self.assertFalse(os.path.exists(session_dir))

    @unittest.skipUnless(os.name == "nt", "Windows directory symlink contract")
    def test_lease_creates_no_artifact_through_redirected_parent(self):
        store = TranscriptStore(self.workspace)
        session_dir = store.resolve_session_dir("session-parent-race")
        outside_dir = os.path.join(self.workspace, "outside-session-directory")
        os.makedirs(session_dir)
        os.makedirs(outside_dir)

        probe_path = session_dir + "-symlink-probe"
        try:
            os.symlink(outside_dir, probe_path, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("directory symlink creation unavailable: %s" % exc)
        else:
            os.rmdir(probe_path)

        os.rmdir(session_dir)
        os.symlink(outside_dir, session_dir, target_is_directory=True)
        try:
            with store.acquire_lease("session-parent-race"):
                pass
            self.assertEqual(os.listdir(outside_dir), [])
        finally:
            if os.path.lexists(session_dir):
                os.rmdir(session_dir)

        with store.acquire_lease("session-parent-race"):
            pass

    @unittest.skipUnless(os.name == "nt", "Windows named mutex contract")
    def test_windows_mutex_timeout_closes_handle_and_reports_conflict(self):
        store = TranscriptStore(self.workspace)
        kernel32 = MagicMock()
        kernel32.CreateMutexW.return_value = 123
        kernel32.WaitForSingleObject.return_value = 0x00000102
        kernel32.CloseHandle.return_value = 1

        with patch("ctypes.WinDLL", return_value=kernel32):
            with self.assertRaisesRegex(
                SessionLeaseConflict,
                "^session log lease is already held: session-timeout$",
            ):
                store._acquire_windows_mutex(
                    "C:\\canonical\\transcript.jsonl",
                    "session-timeout",
                )

        kernel32.CloseHandle.assert_called_once_with(123)

    @unittest.skipUnless(os.name == "nt", "Windows named mutex contract")
    def test_windows_mutex_wait_exception_closes_handle(self):
        store = TranscriptStore(self.workspace)
        kernel32 = MagicMock()
        kernel32.CreateMutexW.return_value = 123
        kernel32.WaitForSingleObject.side_effect = OSError("wait failed")
        kernel32.CloseHandle.return_value = 1

        with patch("ctypes.WinDLL", return_value=kernel32):
            with self.assertRaisesRegex(OSError, "^wait failed$"):
                store._acquire_windows_mutex(
                    "C:\\canonical\\transcript.jsonl",
                    "session-wait-error",
                )

        kernel32.CloseHandle.assert_called_once_with(123)

    @unittest.skipUnless(os.name == "nt", "Windows named mutex contract")
    def test_windows_mutex_accepts_abandoned_ownership(self):
        store = TranscriptStore(self.workspace)
        kernel32 = MagicMock()
        kernel32.CreateMutexW.return_value = 123
        kernel32.WaitForSingleObject.return_value = 0x00000080
        kernel32.ReleaseMutex.return_value = 1
        kernel32.CloseHandle.return_value = 1

        with patch("ctypes.WinDLL", return_value=kernel32):
            handle = store._acquire_windows_mutex(
                "C:\\canonical\\transcript.jsonl",
                "session-abandoned",
            )
            store._release_windows_mutex(handle)

        self.assertEqual(handle, 123)
        kernel32.ReleaseMutex.assert_called_once_with(123)
        kernel32.CloseHandle.assert_called_once_with(123)

    @unittest.skipUnless(os.name == "nt", "Windows named mutex contract")
    def test_windows_mutex_release_failure_still_closes_handle(self):
        store = TranscriptStore(self.workspace)
        kernel32 = MagicMock()
        kernel32.ReleaseMutex.return_value = 0
        kernel32.CloseHandle.return_value = 1

        with patch("ctypes.WinDLL", return_value=kernel32):
            with self.assertRaisesRegex(
                SessionLeaseConflict,
                "^session mutex release failed$",
            ):
                store._release_windows_mutex(123)

        kernel32.CloseHandle.assert_called_once_with(123)

    def test_independent_stores_share_session_lease(self):
        first = TranscriptStore(self.workspace)
        second = TranscriptStore(self.workspace)

        with first.acquire_lease("session-one"):
            with self.assertRaisesRegex(
                SessionLeaseConflict,
                "^session log lease is already held: session-one$",
            ):
                with second.acquire_lease("session-one"):
                    pass

        with second.acquire_lease("session-one"):
            pass

    def test_session_lease_identity_survives_in_root_directory_redirect(self):
        first = TranscriptStore(self.workspace)
        second = TranscriptStore(self.workspace)
        session_a = first.resolve_session_dir("session-a")
        session_b = first.resolve_session_dir("session-b")
        os.makedirs(session_a)
        os.makedirs(session_b)

        with first.acquire_lease("session-a"):
            os.rmdir(session_a)
            try:
                os.symlink(session_b, session_a, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                os.makedirs(session_a)
                self.skipTest("directory symlink creation unavailable: %s" % exc)
            try:
                with self.assertRaisesRegex(
                    SessionLeaseConflict,
                    "^session log lease is already held: session-a$",
                ):
                    with second.acquire_lease("session-a"):
                        pass
            finally:
                os.rmdir(session_a)

    @unittest.skipUnless(os.name == "nt", "Windows named mutex contract")
    def test_windows_processes_share_session_lease(self):
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        release = context.Event()
        process = context.Process(
            target=_hold_transcript_lease,
            args=(self.workspace, ready, release),
        )
        process.start()
        try:
            self.assertTrue(ready.wait(10))
            store = TranscriptStore(self.workspace)
            with self.assertRaisesRegex(
                SessionLeaseConflict,
                "^session log lease is already held: session-process$",
            ):
                with store.acquire_lease("session-process"):
                    pass
        finally:
            release.set()
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(5)
        self.assertEqual(process.exitcode, 0)

    @unittest.skipUnless(os.name == "nt", "Windows named mutex contract")
    def test_windows_process_lease_identity_survives_in_root_directory_redirect(self):
        store = TranscriptStore(self.workspace)
        session_a = store.resolve_session_dir("session-a")
        session_b = store.resolve_session_dir("session-b")
        os.makedirs(session_a)
        os.makedirs(session_b)
        context = multiprocessing.get_context("spawn")
        result = context.Queue()
        process = None

        with store.acquire_lease("session-a"):
            os.rmdir(session_a)
            try:
                os.symlink(session_b, session_a, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                os.makedirs(session_a)
                self.skipTest("directory symlink creation unavailable: %s" % exc)
            try:
                process = context.Process(
                    target=_attempt_transcript_lease,
                    args=(self.workspace, "session-a", result),
                )
                process.start()
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            finally:
                if process is not None and process.is_alive():
                    process.terminate()
                    process.join(5)
                if os.path.lexists(session_a):
                    os.rmdir(session_a)

        self.assertIsNotNone(process)
        self.assertEqual(process.exitcode, 0)
        self.assertEqual(result.get(timeout=2), "conflict")

    def test_session_methods_reject_transcript_paths_and_reference_loader_is_explicit(self):
        store = TranscriptStore(self.workspace)
        store.append_event("session-one", "message", {"content": "one"})
        transcript_path = store.resolve_transcript_path("session-one")

        with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
            store.load_events(transcript_path)
        with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
            with store.acquire_lease(transcript_path):
                pass
        self.assertFalse(store.transcript_exists(transcript_path))
        self.assertEqual(
            store.load_events_from_reference(transcript_path)[0]["payload"]["content"],
            "one",
        )

    def test_transcript_reference_must_stay_inside_sessions_root(self):
        store = TranscriptStore(self.workspace)
        outside_path = os.path.join(self.workspace, "outside", "transcript.jsonl")
        noncanonical_path = os.path.join(store.root, "Case-ID", "transcript.jsonl")

        with self.assertRaisesRegex(ValueError, "^transcript reference is invalid$"):
            store.resolve_transcript_reference(outside_path)
        with self.assertRaisesRegex(ValueError, "^transcript reference is invalid$"):
            store.load_events_from_reference(outside_path)
        with self.assertRaisesRegex(ValueError, "^transcript reference is invalid$"):
            store.resolve_transcript_reference(noncanonical_path)

    def test_session_id_operations_reject_in_root_directory_redirect(self):
        store = TranscriptStore(self.workspace)
        store.append_event("session-b", "message", {"content": "preserve"})
        session_a = os.path.join(store.root, "session-a")
        session_b = store.resolve_session_dir("session-b")
        transcript_b = store.resolve_transcript_path("session-b")
        with open(transcript_b, "rb") as handle:
            original_transcript = handle.read()
        try:
            os.symlink(session_b, session_a, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("directory symlink creation unavailable: %s" % exc)

        try:
            with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                store.resolve_session_dir("session-a")
            with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                store.resolve_transcript_path("session-a")
            with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                store.append_event("session-a", "message", {"content": "overwrite"})
            with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                store.load_events("session-a")
            with open(transcript_b, "rb") as handle:
                self.assertEqual(handle.read(), original_transcript)
        finally:
            os.rmdir(session_a)

    def test_explicit_reference_follows_in_root_alias_to_canonical_session(self):
        store = TranscriptStore(self.workspace)
        store.append_event("session-b", "message", {"content": "canonical"})
        session_a = os.path.join(store.root, "session-a")
        session_b = store.resolve_session_dir("session-b")
        transcript_b = store.resolve_transcript_path("session-b")
        try:
            os.symlink(session_b, session_a, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("directory symlink creation unavailable: %s" % exc)

        try:
            alias_reference = os.path.join(session_a, "transcript.jsonl")
            self.assertEqual(store.resolve_transcript_reference(alias_reference), transcript_b)
            events = store.load_events_from_reference(alias_reference)
            self.assertEqual(events[0]["payload"]["content"], "canonical")
        finally:
            os.rmdir(session_a)

    def test_session_id_operations_reject_in_root_transcript_redirect(self):
        store = TranscriptStore(self.workspace)
        store.append_event("session-b", "message", {"content": "preserve"})
        session_a = store.resolve_session_dir("session-a")
        transcript_a = os.path.join(session_a, "transcript.jsonl")
        transcript_b = store.resolve_transcript_path("session-b")
        os.makedirs(session_a)
        with open(transcript_b, "rb") as handle:
            original_transcript = handle.read()
        try:
            os.symlink(transcript_b, transcript_a)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("file symlink creation unavailable: %s" % exc)

        try:
            with store.acquire_lease("session-a"):
                with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                    store.resolve_transcript_path("session-a")
                with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                    store.append_event("session-a", "message", {"content": "overwrite"})
                with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                    store.load_events("session-a")
                self.assertFalse(store.transcript_exists("session-a"))

            with open(transcript_b, "rb") as handle:
                self.assertEqual(handle.read(), original_transcript)
            self.assertEqual(store.resolve_transcript_reference(transcript_a), transcript_b)
            events = store.load_events_from_reference(transcript_a)
            self.assertEqual(events[0]["payload"]["content"], "preserve")
        finally:
            os.remove(transcript_a)

    def test_session_id_operations_reject_in_root_transcript_hardlink(self):
        store = TranscriptStore(self.workspace)
        store.append_event("session-b", "message", {"content": "preserve"})
        session_a = store.resolve_session_dir("session-a")
        transcript_a = os.path.join(session_a, "transcript.jsonl")
        transcript_b = store.resolve_transcript_path("session-b")
        os.makedirs(session_a)
        with open(transcript_b, "rb") as handle:
            original_transcript = handle.read()
        try:
            os.link(transcript_b, transcript_a)
        except (NotImplementedError, OSError) as exc:
            self.skipTest("hardlink creation unavailable: %s" % exc)

        try:
            with store.acquire_lease("session-a"):
                with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                    store.resolve_transcript_path("session-a")
                with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                    store.append_event("session-a", "message", {"content": "overwrite"})
                with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                    store.load_events("session-a")
                self.assertFalse(store.transcript_exists("session-a"))

            with open(transcript_b, "rb") as handle:
                self.assertEqual(handle.read(), original_transcript)
            with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                store.load_events_from_reference(transcript_a)
        finally:
            os.remove(transcript_a)

    @unittest.skipUnless(os.name == "nt", "Windows handle-first I/O contract")
    def test_append_rejects_parent_redirect_after_resolver_returns(self):
        store = TranscriptStore(self.workspace)
        session_dir = store.resolve_session_dir("session-parent-race")
        outside_dir = os.path.join(self.workspace, "outside-parent-race")
        outside_transcript = os.path.join(outside_dir, "transcript.jsonl")
        os.makedirs(session_dir)
        os.makedirs(outside_dir)
        original_resolve = store.resolve_transcript_path
        replaced = [False]

        def resolve_then_redirect(session_id):
            path = original_resolve(session_id)
            if not replaced[0]:
                os.rmdir(session_dir)
                os.symlink(outside_dir, session_dir, target_is_directory=True)
                replaced[0] = True
            return path

        store.resolve_transcript_path = resolve_then_redirect
        try:
            with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                store.append_event(
                    "session-parent-race",
                    "message",
                    {"content": "do not write outside"},
                )
            self.assertFalse(os.path.exists(outside_transcript))
        finally:
            store.resolve_transcript_path = original_resolve
            if os.path.lexists(session_dir):
                os.rmdir(session_dir)

    @unittest.skipUnless(os.name == "nt", "Windows handle-first I/O contract")
    def test_append_root_creation_rejects_component_redirect_without_outside_artifacts(self):
        store = TranscriptStore(self.workspace)
        outside_dir = os.path.join(self.workspace, "outside-root-race")
        first_component = os.path.join(self.workspace, ".embedagent")
        os.makedirs(outside_dir)
        original_mkdir = os.mkdir
        redirected = [False]

        def mkdir_then_redirect(path, mode=0o777):
            result = original_mkdir(path, mode)
            if os.path.normcase(path) == os.path.normcase(first_component) and not redirected[0]:
                os.rmdir(first_component)
                os.symlink(outside_dir, first_component, target_is_directory=True)
                redirected[0] = True
            return result

        try:
            with patch("embedagent.transcript_store.os.mkdir", side_effect=mkdir_then_redirect):
                with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                    store.append_event(
                        "session-root-race",
                        "message",
                        {"content": "do not create outside"},
                    )
            self.assertEqual(os.listdir(outside_dir), [])
        finally:
            if os.path.lexists(first_component):
                os.rmdir(first_component)

    @unittest.skipUnless(os.name == "nt", "Windows handle-first I/O contract")
    def test_append_rejects_final_symlink_after_resolver_returns(self):
        store = TranscriptStore(self.workspace)
        session_dir = store.resolve_session_dir("session-file-race")
        transcript_path = os.path.join(session_dir, "transcript.jsonl")
        outside_path = os.path.join(self.workspace, "outside-symlink-target.jsonl")
        os.makedirs(session_dir)
        with open(outside_path, "wb") as handle:
            handle.write(b"DO-NOT-TOUCH")
        original_resolve = store.resolve_transcript_path
        replaced = [False]

        def resolve_then_redirect(session_id):
            path = original_resolve(session_id)
            if not replaced[0]:
                os.symlink(outside_path, path)
                replaced[0] = True
            return path

        store.resolve_transcript_path = resolve_then_redirect
        try:
            with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                store.append_event(
                    "session-file-race",
                    "message",
                    {"content": "do not truncate outside"},
                )
            with open(outside_path, "rb") as handle:
                self.assertEqual(handle.read(), b"DO-NOT-TOUCH")
        finally:
            store.resolve_transcript_path = original_resolve
            if os.path.lexists(transcript_path):
                os.remove(transcript_path)

    @unittest.skipUnless(os.name == "nt", "Windows handle-first I/O contract")
    def test_append_rejects_final_hardlink_after_resolver_returns(self):
        store = TranscriptStore(self.workspace)
        session_dir = store.resolve_session_dir("session-hardlink-race")
        transcript_path = os.path.join(session_dir, "transcript.jsonl")
        outside_path = os.path.join(self.workspace, "outside-hardlink-target.jsonl")
        os.makedirs(session_dir)
        with open(outside_path, "wb") as handle:
            handle.write(b"DO-NOT-TOUCH")
        original_resolve = store.resolve_transcript_path
        linked_count = [0]

        def resolve_then_link(session_id):
            path = original_resolve(session_id)
            if not linked_count[0]:
                os.link(outside_path, path)
                linked_count[0] = os.stat(outside_path).st_nlink
            return path

        store.resolve_transcript_path = resolve_then_link
        try:
            with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
                store.append_event(
                    "session-hardlink-race",
                    "message",
                    {"content": "do not truncate outside"},
                )
            with open(outside_path, "rb") as handle:
                self.assertEqual(handle.read(), b"DO-NOT-TOUCH")
            self.assertEqual(os.stat(outside_path).st_nlink, linked_count[0])
        finally:
            store.resolve_transcript_path = original_resolve
            if os.path.lexists(transcript_path):
                os.remove(transcript_path)

    def test_malicious_session_id_cannot_truncate_file_outside_sessions_root(self):
        store = TranscriptStore(self.workspace)
        outside_path = os.path.join(self.workspace, "outside.jsonl")
        with open(outside_path, "w", encoding="utf-8") as handle:
            handle.write("do-not-touch")

        with self.assertRaisesRegex(ValueError, "^session_id is invalid$"):
            store.append_event(outside_path, "message", {"content": "unsafe"})

        with open(outside_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "do-not-touch")

    def test_append_and_load_roundtrip(self):
        store = TranscriptStore(self.workspace)
        store.append_event(
            "sess-roundtrip",
            "session_meta",
            {"current_mode": "build", "started_at": "2026-04-02T00:00:00Z"},
        )
        store.append_event(
            "sess-roundtrip",
            "message",
            {
                "role": "user",
                "message_id": "m-user-1",
                "turn_id": "t-1",
                "step_id": "",
                "content": "continue",
            },
        )
        events = store.load_events("sess-roundtrip")
        self.assertEqual([item["seq"] for item in events], [1, 2])
        self.assertEqual(events[0]["type"], "session_meta")
        self.assertEqual(events[1]["payload"]["content"], "continue")

    def test_returned_events_cannot_corrupt_cache_or_durable_sequence(self):
        store = TranscriptStore(self.workspace)
        appended = store.append_event(
            "sess-cache-isolation",
            "message",
            {"nested": {"values": ["original"]}},
        )
        appended["seq"] = 100
        appended["payload"]["nested"]["values"].append("append-return-mutated")

        loaded = store.load_events("sess-cache-isolation")
        loaded[0]["seq"] = 200
        loaded[0]["payload"]["nested"]["values"].append("load-return-mutated")

        second = store.append_event("sess-cache-isolation", "message", {"content": "second"})
        self.assertEqual(second["seq"], 2)
        cached_events = store.load_events("sess-cache-isolation")
        self.assertEqual([event["seq"] for event in cached_events], [1, 2])
        self.assertEqual(cached_events[0]["payload"]["nested"]["values"], ["original"])

        reopened = TranscriptStore(self.workspace)
        durable_events = reopened.load_events("sess-cache-isolation")
        self.assertEqual([event["seq"] for event in durable_events], [1, 2])
        self.assertEqual(durable_events[0]["payload"]["nested"]["values"], ["original"])

    def test_scan_cache_rejects_same_size_file_replacement(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-cache-identity", "message", {"content": "first"})
        transcript_path = store.resolve_transcript_path("sess-cache-identity")
        replacement_path = transcript_path + ".replacement"
        with open(transcript_path, "rb") as handle:
            original_bytes = handle.read()
        replacement_bytes = original_bytes.replace(b'"first"', b'"other"', 1)
        self.assertEqual(len(replacement_bytes), len(original_bytes))
        with open(replacement_path, "wb") as handle:
            handle.write(replacement_bytes)
        os.replace(replacement_path, transcript_path)

        events = store.load_events("sess-cache-identity")

        self.assertEqual(events[0]["payload"]["content"], "other")

    def test_scan_cache_rejects_same_size_in_place_rewrite(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-cache-version", "message", {"content": "first"})
        transcript_path = store.resolve_transcript_path("sess-cache-version")
        with open(transcript_path, "r+b") as handle:
            original_bytes = handle.read()
            replacement_bytes = original_bytes.replace(b'"first"', b'"other"', 1)
            self.assertEqual(len(replacement_bytes), len(original_bytes))
            handle.seek(0)
            handle.write(replacement_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        events = store.load_events("sess-cache-version")

        self.assertEqual(events[0]["payload"]["content"], "other")

    @unittest.skipUnless(os.name == "nt", "Windows file change token contract")
    def test_scan_cache_rejects_in_place_rewrite_with_restored_mtime(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-cache-change-time", "message", {"content": "first"})
        transcript_path = store.resolve_transcript_path("sess-cache-change-time")
        original_stat = os.stat(transcript_path)
        with open(transcript_path, "r+b") as handle:
            original_bytes = handle.read()
            replacement_bytes = original_bytes.replace(b'"first"', b'"other"', 1)
            self.assertEqual(len(replacement_bytes), len(original_bytes))
            handle.seek(0)
            handle.write(replacement_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.utime(
            transcript_path,
            ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
        )

        events = store.load_events("sess-cache-change-time")

        self.assertEqual(events[0]["payload"]["content"], "other")

    @unittest.skipUnless(os.name == "nt", "Windows file change token contract")
    def test_scan_cache_rescans_when_windows_change_token_is_unavailable(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-cache-no-token", "message", {"content": "first"})
        transcript_path = store.resolve_transcript_path("sess-cache-no-token")

        with patch.object(store, "_windows_change_token", return_value=None):
            first_load = store.load_events("sess-cache-no-token")
            self.assertEqual(first_load[0]["payload"]["content"], "first")
            with open(transcript_path, "r+b") as handle:
                original_bytes = handle.read()
                replacement_bytes = original_bytes.replace(b'"first"', b'"other"', 1)
                handle.seek(0)
                handle.write(replacement_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            second_load = store.load_events("sess-cache-no-token")

        self.assertEqual(second_load[0]["payload"]["content"], "other")

    def test_append_does_not_deepcopy_cached_history(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-linear-append", "message", {"content": "first"})

        def copy_without_history_list(value):
            if isinstance(value, list):
                self.fail("append must not deepcopy the cached event history")
            return deepcopy(value)

        with patch("embedagent.transcript_store.deepcopy", side_effect=copy_without_history_list):
            second = store.append_event(
                "sess-linear-append",
                "message",
                {"content": "second"},
            )

        self.assertEqual(second["seq"], 2)
        self.assertEqual(
            [event["seq"] for event in store.load_events("sess-linear-append")],
            [1, 2],
        )

    def test_load_events_ignores_damaged_tail(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-tail", "session_meta", {"current_mode": "debug"})
        path = store.resolve_transcript_path("sess-tail")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("{bad-json")
        events = store.load_events("sess-tail")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "session_meta")

    def test_load_events_stops_at_sequence_gap(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-gap", "session_meta", {"current_mode": "debug"})
        store.append_event(
            "sess-gap",
            "message",
            {
                "role": "user",
                "message_id": "m-user-1",
                "turn_id": "t-1",
                "step_id": "",
                "content": "continue",
            },
        )
        path = store.resolve_transcript_path("sess-gap")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                '{"schema_version":2,"session_id":"sess-gap","event_id":"evt-gap","seq":5,"ts":"2026-04-04T00:00:00Z","type":"loop_transition","parent_message_id":"","payload":{"reason":"completed"}}\n'
            )
        events = store.load_events("sess-gap")
        self.assertEqual([item["seq"] for item in events], [1, 2])

    def test_append_event_truncates_damaged_tail_before_continuing(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-recover", "session_meta", {"current_mode": "debug"})
        path = store.resolve_transcript_path("sess-recover")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("{bad-json")

        store.append_event(
            "sess-recover",
            "message",
            {
                "role": "user",
                "message_id": "m-user-1",
                "turn_id": "t-1",
                "step_id": "",
                "content": "recovered",
            },
        )

        events = store.load_events("sess-recover")
        self.assertEqual([item["seq"] for item in events], [1, 2])
        self.assertEqual(events[-1]["payload"]["content"], "recovered")

    def test_append_event_keeps_seq_monotonic(self):
        store = TranscriptStore(self.workspace)
        first = store.append_event("sess-seq", "session_meta", {"current_mode": "build"})
        second = store.append_event("sess-seq", "loop_transition", {"reason": "completed"})
        self.assertEqual(first["seq"], 1)
        self.assertEqual(second["seq"], 2)

    def test_append_event_serializes_concurrent_writers(self):
        store = TranscriptStore(self.workspace)
        store.append_event("sess-race", "session_meta", {"current_mode": "build"})
        writer_count = 8
        start = threading.Barrier(writer_count + 1)
        errors = []

        def writer(index):
            try:
                start.wait()
                store.append_event(
                    "sess-race",
                    "message",
                    {
                        "role": "user",
                        "message_id": "m-%s" % index,
                        "turn_id": "t-1",
                        "step_id": "",
                        "content": "message-%s" % index,
                    },
                )
            except Exception as exc:  # pragma: no cover - surfaced by assertion below
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(index,)) for index in range(writer_count)]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        events = store.load_events("sess-race")
        self.assertEqual([item["seq"] for item in events], list(range(1, writer_count + 2)))
        self.assertEqual(
            {item["payload"]["content"] for item in events[1:]},
            {"message-%s" % index for index in range(writer_count)},
        )

    def test_append_event_schema_v2_format(self):
        store = TranscriptStore(self.workspace)
        event = store.append_event(
            "sess-v2",
            "user",
            {"role": "user", "content": "hi", "parent_message_id": ""},
            schema_version=2,
        )
        self.assertEqual(event["schema_version"], 2)
        self.assertEqual(event["type"], "user")
        self.assertIn("parent_message_id", event)
        events = store.load_events("sess-v2")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["schema_version"], 2)
        self.assertEqual(events[0]["type"], "user")
        self.assertIn("parent_message_id", events[0])

    def test_append_event_rejects_non_v2_schema(self):
        store = TranscriptStore(self.workspace)
        with self.assertRaises(ValueError):
            store.append_event("sess-reject", "message", {"role": "user"}, schema_version=0)

    def test_validate_transcript_chain_valid(self):
        store = TranscriptStore(self.workspace)
        store.append_event(
            "sess-valid",
            "user",
            {"role": "user", "content": "first", "message_id": "m-1", "parent_message_id": ""},
            schema_version=2,
        )
        store.append_event(
            "sess-valid",
            "assistant",
            {
                "role": "assistant",
                "content": "second",
                "message_id": "m-2",
                "parent_message_id": "m-1",
            },
            schema_version=2,
        )
        store.append_event(
            "sess-valid",
            "user",
            {"role": "user", "content": "third", "message_id": "m-3", "parent_message_id": "m-2"},
            schema_version=2,
        )
        result = store.validate_transcript_chain("sess-valid")
        self.assertTrue(result["valid"])
        self.assertEqual(result["breaks"], [])

    def test_validate_transcript_chain_broken(self):
        store = TranscriptStore(self.workspace)
        store.append_event(
            "sess-broken",
            "user",
            {"role": "user", "content": "first", "message_id": "m-1", "parent_message_id": ""},
            schema_version=2,
        )
        store.append_event(
            "sess-broken",
            "assistant",
            {
                "role": "assistant",
                "content": "second",
                "message_id": "m-2",
                "parent_message_id": "m-nonexistent",
            },
            schema_version=2,
        )
        result = store.validate_transcript_chain("sess-broken")
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["breaks"]), 1)
        self.assertIn("parent_not_found", result["breaks"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
