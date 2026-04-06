from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ToolSpecV2:
    name: str
    description: str
    prompt: str
    input_schema: Dict[str, object]
    result_budget_policy: str
    tags: List[str] = field(default_factory=list)
