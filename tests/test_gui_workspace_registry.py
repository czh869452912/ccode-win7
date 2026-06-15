import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedagent.frontend.gui.backend.workspace_registry import (
    WorkspaceRegistry,
    canonical_workspace_path,
    workspace_id_for_path,
)


class TestGuiWorkspaceRegistry(unittest.TestCase):
    def test_workspace_id_is_stable_for_canonical_path(self):
        with tempfile.TemporaryDirectory() as root:
            nested = os.path.join(root, ".", "demo")
            os.mkdir(os.path.join(root, "demo"))
            self.assertEqual(
                workspace_id_for_path(nested),
                workspace_id_for_path(os.path.realpath(os.path.join(root, "demo"))),
            )

    def test_upsert_lists_existing_workspace_with_label_and_timestamp(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            registry = WorkspaceRegistry(
                storage_path=storage,
                clock=lambda: "2026-06-15T10:00:00Z",
            )

            record = registry.upsert_path(workspace)
            records = registry.list_workspaces()

        self.assertEqual(record["id"], workspace_id_for_path(workspace))
        self.assertEqual(record["path"], canonical_workspace_path(workspace))
        self.assertEqual(record["label"], "project-a")
        self.assertEqual(record["created_at"], "2026-06-15T10:00:00Z")
        self.assertEqual(record["last_opened_at"], "2026-06-15T10:00:00Z")
        self.assertEqual(records[0]["exists"], True)

    def test_upsert_existing_workspace_preserves_created_at_and_updates_last_opened(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            ticks = iter(["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"])
            registry = WorkspaceRegistry(storage_path=storage, clock=lambda: next(ticks))

            first = registry.upsert_path(workspace)
            second = registry.upsert_path(workspace, label="Renamed")

        self.assertEqual(first["created_at"], "2026-06-15T10:00:00Z")
        self.assertEqual(second["created_at"], "2026-06-15T10:00:00Z")
        self.assertEqual(second["last_opened_at"], "2026-06-15T11:00:00Z")
        self.assertEqual(second["label"], "Renamed")

    def test_remove_deletes_registry_entry_without_touching_workspace_files(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            marker = os.path.join(workspace, "README.md")
            with open(marker, "w", encoding="utf-8") as handle:
                handle.write("kept")
            registry = WorkspaceRegistry(storage_path=storage)
            record = registry.upsert_path(workspace)

            removed = registry.remove(record["id"])
            self.assertEqual(removed, True)
            self.assertTrue(os.path.exists(marker))
            self.assertEqual(registry.list_workspaces(), [])

    def test_missing_workspace_is_listed_with_exists_false(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            workspace = os.path.join(root, "project-a")
            os.mkdir(workspace)
            registry = WorkspaceRegistry(storage_path=storage)
            record = registry.upsert_path(workspace)
            os.rmdir(workspace)

            records = registry.list_workspaces()

        self.assertEqual(records[0]["id"], record["id"])
        self.assertEqual(records[0]["exists"], False)

    def test_corrupt_registry_file_recovers_to_empty_list(self):
        with tempfile.TemporaryDirectory() as root:
            storage = os.path.join(root, "registry.json")
            with open(storage, "w", encoding="utf-8") as handle:
                handle.write("{")
            registry = WorkspaceRegistry(storage_path=storage)

            self.assertEqual(registry.list_workspaces(), [])
            registry.upsert_path(root)

            with open(storage, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        self.assertEqual(payload["version"], 1)
        self.assertEqual(len(payload["workspaces"]), 1)


if __name__ == "__main__":
    unittest.main()
