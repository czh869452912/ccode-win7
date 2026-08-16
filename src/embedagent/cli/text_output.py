from __future__ import annotations

import sys
from typing import Any


def _prepare_standard_stream(stream: Any) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="replace")


def prepare_cli_standard_streams() -> None:
    _prepare_standard_stream(sys.stdout)
    _prepare_standard_stream(sys.stderr)
