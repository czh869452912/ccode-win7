from __future__ import annotations

import json
import sys
from typing import Optional, TextIO

from embedagent.cli.result import CliResult, write_failure


def write_result(
    result: CliResult,
    output: str = "text",
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    if not isinstance(result, CliResult):
        raise TypeError("result must be a CliResult")
    selected_output = str(output or "text")
    out = stdout if stdout is not None else sys.stdout
    error = stderr if stderr is not None else sys.stderr
    if selected_output == "json":
        out.write(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        return result.exit_code
    if selected_output != "text":
        raise ValueError("unsupported CLI output format")
    if result.final_text:
        out.write(result.final_text)
        if not result.final_text.endswith("\n"):
            out.write("\n")
    if result.failure is not None:
        write_failure(result.failure, stream=error)
    return result.exit_code
