"""Tests for ShadowGitSnapshot service."""

import os
import tempfile
import time
import unittest
from datetime import datetime, timezone

from embedagent.services.shadow_git import ShadowGitSnapshot
from embedagent.tools._base import ToolError


class TestShadowGitSnapshot(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Initialize git repo
        import subprocess

        subprocess.run(["git", "init"], cwd=self.temp_dir, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=self.temp_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.temp_dir,
            capture_output=True,
        )
        # Create initial commit
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("initial content\n")
        subprocess.run(["git", "add", "."], cwd=self.temp_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=self.temp_dir,
            capture_output=True,
        )
        self.snapshot = ShadowGitSnapshot(self.temp_dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_snapshot_success(self):
        # Modify a file
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("modified content\n")

        snapshot_id = self.snapshot.create_snapshot("test_reason")
        self.assertIsNotNone(snapshot_id)
        self.assertTrue(len(snapshot_id) > 0)

        # Check metadata file exists
        meta_path = os.path.join(
            self.temp_dir, ".embedagent", "snapshots", "{}.json".format(snapshot_id)
        )
        self.assertTrue(os.path.exists(meta_path))

        # Check stash entry exists
        import subprocess

        result = subprocess.run(
            ["git", "stash", "list"],
            cwd=self.temp_dir,
            capture_output=True,
            text=True,
        )
        self.assertIn(snapshot_id, result.stdout)

    def test_list_snapshots_returns_metadata(self):
        # Create first snapshot with changes to tracked file
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("content 1\n")
        # Stage and commit so file is tracked
        import subprocess

        subprocess.run(["git", "add", "."], cwd=self.temp_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "content 1"], cwd=self.temp_dir, capture_output=True)

        # Now modify the tracked file and create first snapshot
        with open(test_file, "w") as f:
            f.write("modified content 1\n")
        sid1 = self.snapshot.create_snapshot("reason_1")
        time.sleep(1.1)

        # Modify again and create second snapshot
        with open(test_file, "w") as f:
            f.write("modified content 2\n")
        sid2 = self.snapshot.create_snapshot("reason_2")

        snapshots = self.snapshot.list_snapshots()
        self.assertEqual(len(snapshots), 2)

        # Check metadata keys
        for snap in snapshots:
            self.assertIn("id", snap)
            self.assertIn("created_at", snap)
            self.assertIn("reason", snap)
            self.assertIn("branch", snap)
            self.assertIn("commit_hash", snap)

        # Check sorted by created_at descending
        self.assertEqual(snapshots[0]["id"], sid2)
        self.assertEqual(snapshots[1]["id"], sid1)

    def test_restore_snapshot_recovers_files(self):
        # Create snapshot with changes
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("before snapshot\n")

        snapshot_id = self.snapshot.create_snapshot("restore_test")

        # At this point, the working directory is clean (changes stashed)
        # Restore should bring back the stashed changes
        success = self.snapshot.restore_snapshot(snapshot_id)
        self.assertTrue(success)

        # Check content restored
        with open(test_file, "r") as f:
            content = f.read()
        self.assertEqual(content, "before snapshot\n")

    def test_delete_snapshot_removes_metadata_and_stash(self):
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("to delete\n")

        snapshot_id = self.snapshot.create_snapshot("delete_test")

        success = self.snapshot.delete_snapshot(snapshot_id)
        self.assertTrue(success)

        # Check metadata removed
        meta_path = os.path.join(
            self.temp_dir, ".embedagent", "snapshots", "{}.json".format(snapshot_id)
        )
        self.assertFalse(os.path.exists(meta_path))

        # Check stash dropped
        import subprocess

        result = subprocess.run(
            ["git", "stash", "list"],
            cwd=self.temp_dir,
            capture_output=True,
            text=True,
        )
        self.assertNotIn(snapshot_id, result.stdout)

    def test_cleanup_old_snapshots(self):
        # Create a snapshot
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("cleanup test\n")

        snapshot_id = self.snapshot.create_snapshot("cleanup_test")

        # Mock metadata with old timestamp
        meta_path = os.path.join(
            self.temp_dir, ".embedagent", "snapshots", "{}.json".format(snapshot_id)
        )
        with open(meta_path, "r") as f:
            metadata = __import__("json").load(f)
        metadata["created_at"] = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        with open(meta_path, "w") as f:
            __import__("json").dump(metadata, f)

        result = self.snapshot.cleanup_old_snapshots(max_age_hours=1)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["retained"], 0)

        # Verify metadata removed
        self.assertFalse(os.path.exists(meta_path))

    def test_snapshot_non_git_repo_raises_error(self):
        non_git_dir = tempfile.mkdtemp()
        try:
            with self.assertRaises(ToolError):
                ShadowGitSnapshot(non_git_dir)
        finally:
            import shutil

            shutil.rmtree(non_git_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
