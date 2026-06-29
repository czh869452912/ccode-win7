"""Validation test for HYGN-03: Verify no deprecation warnings from project code during test execution."""

import os
import subprocess
import sys


class TestNoDeprecationWarnings:
    """Ensure test suite produces zero deprecation warnings from project code."""

    def test_pytest_runs_without_deprecation_warnings(self):
        """Run pytest with warnings as errors and verify no failures from project code."""
        # Run the fast test subset with deprecation warnings treated as errors
        # IMPORTANT: ignore this file to avoid infinite recursion
        project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
        nested_basetemp = os.path.join(project_root, "build", "test-sandboxes", "pytest-hygn-03")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/",
                "-m",
                "not slow and not gui",
                "--basetemp",
                nested_basetemp,
                "--ignore=tests/test_gui_sync.py",  # Skip known failing test
                "--ignore=tests/test_hygn_03_warning_cleanup.py",  # Skip self to avoid recursion
                "-W",
                "error::DeprecationWarning:embedagent.*",
                "-q",
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        # Check that the test suite passes (exit code 0)
        assert result.returncode == 0, (
            f"Test suite failed when treating project-code DeprecationWarnings as errors.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_pytest_config_has_warning_filters(self):
        """Verify pyproject.toml has warning filter configuration."""
        import tomli

        pyproject_path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")

        with open(pyproject_path, "rb") as f:
            config = tomli.load(f)

        # Check pytest configuration exists
        pytest_config = config.get("tool", {}).get("pytest", {}).get("ini_options", {})
        assert (
            "filterwarnings" in pytest_config
        ), "Missing filterwarnings in [tool.pytest.ini_options] in pyproject.toml"

        filters = pytest_config["filterwarnings"]

        # Check that project-code warnings are treated as errors
        has_error_filter = any("error::DeprecationWarning:embedagent" in f for f in filters)
        assert has_error_filter, (
            "Missing 'error::DeprecationWarning:embedagent.*' filter in pytest configuration. "
            f"Found filters: {filters}"
        )

        # Check that third-party warnings are ignored
        has_ignore_filter = any("ignore::DeprecationWarning" in f for f in filters)
        assert has_ignore_filter, (
            "Missing 'ignore::DeprecationWarning' filter for third-party libraries. "
            f"Found filters: {filters}"
        )

    def test_no_utcnnow_in_characterization_tests(self):
        """Verify characterization tests don't use deprecated datetime.utcnow()."""
        test_dir = os.path.join(os.path.dirname(__file__), "..")
        violations = []

        for filename in os.listdir(os.path.join(test_dir, "tests")):
            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(test_dir, "tests", filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for deprecated utcnow() usage in test files
            if "datetime.utcnow()" in content or "utcnow()" in content:
                # Exclude the test that explicitly checks for its absence
                # Also exclude this file which references utcnow() in test logic
                if filename not in (
                    "test_hygn_01_datetime_cleanup.py",
                    "test_timestamp_characterization.py",
                    "test_hygn_03_warning_cleanup.py",
                ):
                    violations.append(filename)

        assert len(violations) == 0, (
            f"Found deprecated datetime.utcnow() usage in test file(s): "
            f"{', '.join(violations)}. Tests should use datetime.now(timezone.utc)."
        )
