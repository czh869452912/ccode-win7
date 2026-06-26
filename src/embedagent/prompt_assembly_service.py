from __future__ import annotations

from typing import Any


class PromptAssemblyService(object):
    def should_append_workflow_prompt(self, workflow_prompt: Any, existing_messages) -> bool:
        if workflow_prompt is None:
            return False
        mode_name = str(getattr(workflow_prompt, "mode_name", "") or "")
        pack_name = str(getattr(workflow_prompt, "pack_name", "") or "")
        discipline_label = str(getattr(workflow_prompt, "discipline_label", "") or "")
        for message in list(existing_messages or []):
            if getattr(message, "role", "") != "system":
                continue
            if getattr(message, "kind", "") != "workflow_prompt":
                continue
            metadata = getattr(message, "metadata", {}) or {}
            if str(metadata.get("mode_name") or "") != mode_name:
                continue
            metadata_pack = str(metadata.get("pack_name") or "")
            metadata_discipline = str(metadata.get("discipline_label") or "")
            if pack_name and metadata_pack == pack_name:
                return False
            if metadata_discipline == discipline_label:
                return False
        return True
