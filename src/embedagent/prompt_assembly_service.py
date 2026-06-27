from __future__ import annotations

from typing import Any, Callable, Dict, Optional


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

    def append_workflow_prompt_messages(
        self,
        workflow_prompt: Any,
        existing_messages: Any,
        add_system_message: Callable[..., Any],
        on_message: Optional[Callable[[Any], None]] = None,
    ) -> bool:
        if not self.should_append_workflow_prompt(workflow_prompt, existing_messages):
            return False
        for index, content in enumerate(list(getattr(workflow_prompt, "prompt_units", []) or [])):
            workflow_message = add_system_message(
                content,
                kind="workflow_prompt",
                metadata={
                    "mode_name": str(workflow_prompt.mode_name or ""),
                    "discipline_label": str(workflow_prompt.discipline_label or ""),
                    "pack_name": str(workflow_prompt.pack_name or ""),
                    "unit_index": index,
                },
            )
            if on_message is not None:
                on_message(workflow_message)
        return True

    def message_event_payload(self, message: Any) -> Dict[str, Any]:
        return {
            "role": message.role,
            "content": message.content,
            "message_id": message.message_id,
            "parent_message_id": message.parent_message_id,
            "turn_id": message.turn_id,
            "step_id": message.step_id,
            "kind": message.kind,
            "metadata": dict(message.metadata),
            "replaced_by_refs": list(message.replaced_by_refs),
        }
