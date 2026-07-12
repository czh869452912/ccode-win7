"""Shadow Git snapshot service for workspace state management."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from embedagent_core.tool_contracts import ToolError

logger = logging.getLogger(__name__)


class ShadowGitSnapshot(object):
    """Creates and manages lightweight git-based workspace snapshots."""

    def __init__(self, workspace: str, snapshot_dir: str = ".embedagent/snapshots") -> None:
        self.workspace = workspace
        self.snapshot_dir = os.path.join(workspace, *snapshot_dir.split("/"))
        self._ensure_snapshot_dir()
        self._ensure_git_repo()

    def _ensure_snapshot_dir(self) -> None:
        if not os.path.isdir(self.snapshot_dir):
            os.makedirs(self.snapshot_dir)
        # Ensure snapshot directory is gitignored so metadata files
        # don't get stashed by git stash push --include-untracked
        gitignore_path = os.path.join(os.path.dirname(self.snapshot_dir), ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("snapshots/\n")

    def _ensure_git_repo(self) -> None:
        git_dir = os.path.join(self.workspace, ".git")
        if not os.path.exists(git_dir):
            raise ToolError("工作区不是 Git 仓库，无法创建快照。")

    def _run_git(self, args: List[str]) -> Dict[str, Any]:
        import subprocess

        command = ["git", "-C", self.workspace] + args
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _find_stash_index(self, snapshot_id: str) -> Optional[int]:
        result = self._run_git(["stash", "list"])
        if result["exit_code"] != 0:
            return None
        for line in result["stdout"].splitlines():
            line = line.strip()
            if not line:
                continue
            # Format: stash@{N}: message
            if ":" in line:
                idx_str = line.split(":", 1)[0]
                if idx_str.startswith("stash@{") and idx_str.endswith("}"):
                    stash_msg = line.split(":", 1)[1].strip()
                    if snapshot_id in stash_msg:
                        try:
                            return int(idx_str[len("stash@{") : -1])
                        except ValueError:
                            continue
        return None

    def create_snapshot(self, reason: str = "") -> str:
        snapshot_id = "{}-{}".format(
            uuid.uuid4().hex[:8],
            int(time.time()),
        )

        # Get current branch
        branch_result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch_result["stdout"].strip() if branch_result["exit_code"] == 0 else "unknown"

        # Get current commit hash
        commit_result = self._run_git(["rev-parse", "HEAD"])
        commit_hash = (
            commit_result["stdout"].strip() if commit_result["exit_code"] == 0 else "unknown"
        )

        # Create stash with snapshot ID in message
        stash_msg = "shadow:{}:{}".format(snapshot_id, reason or "manual")
        stash_result = self._run_git(
            [
                "stash",
                "push",
                "--include-untracked",
                "--message",
                stash_msg,
            ]
        )

        has_stash = stash_result["exit_code"] == 0
        if not has_stash:
            # Check if it's just "no local changes" - that's okay
            stderr = stash_result.get("stderr", "")
            if "No local changes to save" not in stderr:
                raise ToolError("创建快照失败：{}".format(stderr))

        # Write metadata
        metadata = {
            "id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "branch": branch,
            "commit_hash": commit_hash,
            "has_stash": has_stash,
        }
        meta_path = os.path.join(self.snapshot_dir, "{}.json".format(snapshot_id))
        os.makedirs(self.snapshot_dir, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        logger.info("Created snapshot %s on branch %s", snapshot_id, branch)
        return snapshot_id

    def restore_snapshot(self, snapshot_id: str) -> bool:
        meta_path = os.path.join(self.snapshot_dir, "{}.json".format(snapshot_id))
        if not os.path.exists(meta_path):
            logger.warning("Snapshot %s not found", snapshot_id)
            return False

        # Read metadata to check if snapshot has a stash
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, IOError):
            metadata = {}

        has_stash = metadata.get("has_stash", True)
        if not has_stash:
            logger.info("Snapshot %s has no stash (empty snapshot)", snapshot_id)
            return True

        stash_index = self._find_stash_index(snapshot_id)
        if stash_index is None:
            logger.warning("Stash entry for snapshot %s not found", snapshot_id)
            return False

        stash_ref = "stash@{" + str(stash_index) + "}"
        result = self._run_git(["stash", "pop", stash_ref])
        if result["exit_code"] != 0:
            logger.warning("Failed to restore snapshot %s: %s", snapshot_id, result["stderr"])
            return False

        logger.info("Restored snapshot %s", snapshot_id)
        return True

    def list_snapshots(self) -> List[Dict[str, Any]]:
        snapshots = []
        if not os.path.isdir(self.snapshot_dir):
            return snapshots

        for filename in os.listdir(self.snapshot_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self.snapshot_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                snapshots.append(metadata)
            except (json.JSONDecodeError, IOError) as exc:
                logger.warning("Failed to read snapshot metadata %s: %s", filename, exc)
                continue

        # Sort by created_at descending
        snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return snapshots

    def delete_snapshot(self, snapshot_id: str) -> bool:
        meta_path = os.path.join(self.snapshot_dir, "{}.json".format(snapshot_id))
        if not os.path.exists(meta_path):
            logger.warning("Snapshot %s not found for deletion", snapshot_id)
            return False

        # Drop stash entry if exists
        stash_index = self._find_stash_index(snapshot_id)
        if stash_index is not None:
            stash_ref = "stash@{" + str(stash_index) + "}"
            result = self._run_git(["stash", "drop", stash_ref])
            if result["exit_code"] != 0:
                logger.warning(
                    "Failed to drop stash for snapshot %s: %s", snapshot_id, result["stderr"]
                )
            else:
                logger.info("Dropped stash for snapshot %s", snapshot_id)
        else:
            logger.info("No stash found for snapshot %s", snapshot_id)

        # Remove metadata file
        try:
            os.remove(meta_path)
            logger.info("Deleted snapshot %s", snapshot_id)
            return True
        except OSError as exc:
            logger.warning("Failed to delete snapshot metadata %s: %s", snapshot_id, exc)
            return False

    def cleanup_old_snapshots(self, max_age_hours: int = 24) -> Dict[str, int]:
        deleted = 0
        retained = 0
        cutoff = time.time() - (max_age_hours * 3600)

        for snapshot in self.list_snapshots():
            snapshot_id = snapshot.get("id")
            if not snapshot_id:
                continue

            created_at_str = snapshot.get("created_at", "")
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                created_timestamp = created_at.timestamp()
            except (ValueError, AttributeError):
                logger.warning(
                    "Invalid created_at for snapshot %s: %s", snapshot_id, created_at_str
                )
                retained += 1
                continue

            if created_timestamp < cutoff:
                if self.delete_snapshot(snapshot_id):
                    deleted += 1
                else:
                    retained += 1
            else:
                retained += 1

        return {"deleted": deleted, "retained": retained}
