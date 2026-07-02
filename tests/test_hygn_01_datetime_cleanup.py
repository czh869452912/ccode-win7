"""Validation test for HYGN-01: Verify zero datetime.utcnow() calls remain in source code."""

import ast
import os


class TestNoDeprecatedDatetime:
    """Ensure no deprecated datetime.utcnow() calls exist in source code."""

    def _find_python_files(self):
        """Find all Python files in src/ directory."""
        src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
        python_files = []
        for root, _, files in os.walk(src_dir):
            for filename in files:
                if filename.endswith(".py"):
                    python_files.append(os.path.join(root, filename))
        return python_files

    def _check_file_for_utcnnow(self, filepath):
        """Check if a file contains datetime.utcnow() calls."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []  # Skip files with syntax errors

        occurrences = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr == "utcnow":
                    # Check if it's datetime.utcnow
                    if isinstance(node.value, ast.Name) and node.value.id == "datetime":
                        occurrences.append(filepath)
                    # Check if it's obj.utcnow where obj might be datetime
                    elif isinstance(node.value, ast.Attribute):
                        if node.value.attr == "datetime":
                            occurrences.append(filepath)
        return occurrences

    def test_zero_utcnnow_calls_in_source(self):
        """Verify no datetime.utcnow() calls exist in src/ directory."""
        python_files = self._find_python_files()
        violations = []

        for filepath in python_files:
            occurrences = self._check_file_for_utcnnow(filepath)
            if occurrences:
                # Get relative path for cleaner output
                rel_path = os.path.relpath(filepath, os.path.join(os.path.dirname(__file__), ".."))
                violations.append(rel_path)

        assert len(violations) == 0, (
            f"Found datetime.utcnow() calls in {len(violations)} file(s): "
            f"{', '.join(violations)}. All datetime.utcnow() calls must be replaced "
            f"with datetime.now(timezone.utc)."
        )

    def test_timezone_imported_in_modified_files(self):
        """Verify all files using datetime.now(timezone.utc) import timezone."""
        files_to_check = [
            "src/embedagent/session.py",
            "src/embedagent/session_store.py",
            "src/embedagent/session_runtime.py",
            "src/embedagent/project_memory.py",
            "src/embedagent_host/inprocess_adapter.py",
            "src/embedagent/plan_store.py",
            "src/embedagent/transcript_store.py",
            "src/embedagent/session_restore.py",
        ]

        base_dir = os.path.join(os.path.dirname(__file__), "..")
        violations = []

        for rel_path in files_to_check:
            filepath = os.path.join(base_dir, rel_path)
            if not os.path.exists(filepath):
                violations.append(f"{rel_path}: file not found")
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Check that timezone is imported from datetime
            if "from datetime import" not in content or "timezone" not in content:
                violations.append(f"{rel_path}: missing timezone import")

            # Check that datetime.now(timezone.utc) is used
            if "datetime.now(timezone.utc)" not in content:
                violations.append(f"{rel_path}: missing datetime.now(timezone.utc) usage")

        assert len(violations) == 0, f"Found {len(violations)} violations: {'; '.join(violations)}"
