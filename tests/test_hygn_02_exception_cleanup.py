"""Validation test for HYGN-02: Verify zero bare 'except Exception:' blocks remain in source code."""

import ast
import os


class TestNoBareExceptBlocks:
    """Ensure no bare 'except Exception:' blocks exist in source code."""

    def _find_python_files(self):
        """Find all Python files in src/ directory."""
        src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
        python_files = []
        for root, _, files in os.walk(src_dir):
            for filename in files:
                if filename.endswith(".py"):
                    python_files.append(os.path.join(root, filename))
        return python_files

    def _check_file_for_bare_except(self, filepath):
        """Check if a file contains bare 'except Exception:' blocks."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []  # Skip files with syntax errors

        occurrences = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check if it's a bare 'except Exception:'
                if node.type is None:
                    # This is 'except:' which catches everything
                    occurrences.append((filepath, node.lineno, "bare except:"))
                elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    # This is 'except Exception:'
                    occurrences.append((filepath, node.lineno, "except Exception:"))
        return occurrences

    def test_zero_bare_except_blocks_in_source(self):
        """Verify no bare 'except Exception:' blocks exist in src/ directory."""
        python_files = self._find_python_files()
        violations = []

        for filepath in python_files:
            occurrences = self._check_file_for_bare_except(filepath)
            for occ in occurrences:
                rel_path = os.path.relpath(filepath, os.path.join(os.path.dirname(__file__), ".."))
                violations.append(f"{rel_path}:{occ[1]} ({occ[2]})")

        assert len(violations) == 0, (
            f"Found {len(violations)} bare except block(s): "
            f"{'; '.join(violations)}. All 'except Exception:' blocks must be replaced "
            f"with specific exception types (e.g., except (OSError, ValueError):)."
        )

    def test_files_use_specific_exceptions(self):
        """Verify modified files use specific exception types."""
        files_expected_patterns = {
            "src/embedagent_core/permissions.py": [
                "OSError",
                "JSONDecodeError",
                "ValueError",
            ],
            "src/embedagent/workflow_packages/c_cpp/task_store.py": [
                "OSError",
                "JSONDecodeError",
                "ValueError",
            ],
            "src/embedagent/session_store.py": ["OSError", "JSONDecodeError", "ValueError"],
            "src/embedagent/project_memory.py": ["OSError", "ValueError"],
            "src/embedagent/workspace_recipes.py": ["OSError", "JSONDecodeError", "ValueError"],
            "src/embedagent/tool_commit.py": ["OSError", "ValueError", "TypeError"],
            "src/embedagent/core/adapter.py": ["OSError", "ValueError"],
            "src/embedagent/tools/discovery_ops.py": [
                "OSError",
                "UnicodeDecodeError",
                "ValueError",
            ],
            "src/embedagent/frontend/gui/launcher.py": ["OSError", "ValueError", "TypeError"],
            "src/embedagent/frontend/gui/backend/server.py": [
                "OSError",
                "ValueError",
                "TypeError",
                "RuntimeError",
            ],
            "src/embedagent/frontend/tui/services/workspace.py": [
                "OSError",
                "ValueError",
                "TypeError",
            ],
            "src/embedagent/frontend/tui/services/sessions.py": [
                "OSError",
                "JSONDecodeError",
                "ValueError",
            ],
            "src/embedagent/frontend/tui/services/timeline.py": [
                "OSError",
                "ValueError",
                "TypeError",
            ],
            "src/embedagent/frontend/tui/services/artifacts.py": [
                "OSError",
                "ValueError",
                "TypeError",
            ],
            "src/embedagent/frontend/tui/layout.py": ["ValueError", "TypeError"],
            "src/embedagent_host/inprocess_adapter.py": ["OSError", "ValueError", "TypeError"],
        }

        base_dir = os.path.join(os.path.dirname(__file__), "..")
        violations = []

        for rel_path, expected_exceptions in files_expected_patterns.items():
            filepath = os.path.join(base_dir, rel_path)
            if not os.path.exists(filepath):
                violations.append(f"{rel_path}: file not found")
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Check that at least one specific exception type is used
            has_specific = any(exc in content for exc in expected_exceptions)
            if not has_specific:
                violations.append(
                    f"{rel_path}: missing specific exception types "
                    f"(expected one of: {', '.join(expected_exceptions)})"
                )

        assert len(violations) == 0, f"Found {len(violations)} violations: {'; '.join(violations)}"
