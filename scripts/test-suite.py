"""Run EmbedAgent test feedback partitions through one stable entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import List, Sequence

REGULAR_EXPRESSION = "not release and not performance"
PRE_PUSH_EXPRESSION = "not release and not performance and not slow and not gui"


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
