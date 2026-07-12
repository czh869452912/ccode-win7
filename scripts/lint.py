"""Run the repository lint checks with one cross-platform entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import List, Sequence

DEFAULT_TARGETS = (
    "src/",
    "packages/embedagent-core/src/",
    "packages/embedagent-protocol/src/",
    "tests/",
    "scripts/lint.py",
)


def _run(command: Sequence[str]) -> int:
    print("+ " + " ".join(command), flush=True)
    return subprocess.call(list(command))


def _run_all(commands: Sequence[Sequence[str]]) -> int:
    for command in commands:
        result = _run(command)
        if result != 0:
            return result
    return 0


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(description="Run ruff and black for EmbedAgent.")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply safe ruff fixes and black formatting instead of check-only mode.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=list(DEFAULT_TARGETS),
        help="Files or directories to lint. Defaults to product/workspace sources and tests.",
    )
    args = parser.parse_args(list(argv))

    targets: List[str] = list(args.targets or DEFAULT_TARGETS)
    if args.fix:
        commands = (
            (sys.executable, "-m", "ruff", "check", "--fix") + tuple(targets),
            (sys.executable, "-m", "black") + tuple(targets),
        )
    else:
        commands = (
            (sys.executable, "-m", "ruff", "check") + tuple(targets),
            (sys.executable, "-m", "black", "--check") + tuple(targets),
        )
    return _run_all(commands)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
