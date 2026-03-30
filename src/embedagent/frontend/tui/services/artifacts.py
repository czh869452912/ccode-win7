from __future__ import annotations

from typing import Any, Dict, List


class ArtifactService(object):
    def __init__(self, adapter) -> None:
        self.adapter = adapter

    def list_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        method = getattr(self.adapter, "list_artifacts", None)
        if callable(method):
            try:
                return method(limit=limit)
            except Exception:
                return []
        return []

    def read_item(self, reference: str) -> Dict[str, Any]:
        method = getattr(self.adapter, "read_artifact", None)
        if callable(method):
            return method(reference)
        raise ValueError("当前适配器不支持读取 artifact。")
