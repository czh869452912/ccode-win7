"""Run EmbedAgent test feedback partitions through one stable entry point."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

REGULAR_EXPRESSION = "not release and not performance"
PRE_PUSH_EXPRESSION = "not release and not performance and not slow and not gui"


def primary_partition(marker_names: Iterable[str]) -> str:
    names = frozenset(marker_names)
    if "release" in names and "performance" in names:
        raise ValueError("test cannot be both release and performance")
    if "release" in names:
        return "release"
    if "performance" in names:
        return "performance"
    return "regular"


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return (prefix + "." if prefix else "") + node.attr
    return ""


def _literal_strings(node: ast.AST) -> Tuple[str, ...]:
    values = []
    for child in ast.walk(node):
        if isinstance(child, ast.Str):
            values.append(str(child.s))
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.append(child.value)
    return tuple(values)


def nested_full_pytest_violations(test_root: Path) -> Tuple[str, ...]:
    root = Path(test_root).resolve()
    violations = []
    for path in sorted(root.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node.func) not in (
                "subprocess.call",
                "subprocess.Popen",
                "subprocess.run",
            ):
                continue
            values = _literal_strings(node)
            normalized = tuple(value.rstrip("/\\") for value in values)
            if "-m" in values and "pytest" in values and "tests" in normalized:
                violations.append("%s:%d" % (path.relative_to(root).as_posix(), node.lineno))
    return tuple(violations)


def _parser():
    parser = argparse.ArgumentParser(description="Run an EmbedAgent test suite partition.")
    commands = parser.add_subparsers(dest="command", required=True)

    tdd = commands.add_parser("tdd", help="Run exact test nodes or files.")
    tdd.add_argument("targets", nargs="+")

    commands.add_parser("failed", help="Rerun failures in the regular fast partition.")
    commands.add_parser("pre-push", help="Run the local fast partition.")

    full = commands.add_parser("full", help="Run all regular Python tests.")
    full.add_argument("--coverage", action="store_true")

    commands.add_parser("release", help="Run release and packaging tests.")
    commands.add_parser("performance", help="Run explicit performance tests.")
    return parser


def _partition_command(expression: str) -> List[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-m",
        expression,
        "--durations=20",
    ]


def build_command(argv: Sequence[str]) -> List[str]:
    args = _parser().parse_args(list(argv))
    if args.command == "tdd":
        return (
            [sys.executable, "-m", "pytest"]
            + list(args.targets)
            + [
                "-q",
                "-x",
                "--tb=short",
            ]
        )
    if args.command == "failed":
        return _partition_command(PRE_PUSH_EXPRESSION) + ["--lf", "-q", "-x", "--tb=short"]
    if args.command == "pre-push":
        return _partition_command(PRE_PUSH_EXPRESSION)
    if args.command == "full":
        command = _partition_command(REGULAR_EXPRESSION)
        if args.coverage:
            command.extend(
                (
                    "--cov",
                    "--cov-config=pyproject.toml",
                    "--cov-report=xml",
                    "--cov-report=term-missing",
                )
            )
        return command
    if args.command == "release":
        return _partition_command("release")
    if args.command == "performance":
        return _partition_command("performance")
    raise ValueError("unsupported test suite command: %s" % args.command)


def _run(command: Sequence[str]) -> int:
    print("+ " + " ".join(command), flush=True)
    return subprocess.call(list(command))


def main(argv: Sequence[str] = ()) -> int:
    return _run(build_command(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
