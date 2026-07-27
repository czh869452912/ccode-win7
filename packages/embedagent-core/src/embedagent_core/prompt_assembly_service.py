from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List


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

    def workflow_prompt_event_payloads(
        self,
        workflow_prompt: Any,
        existing_messages: Any,
    ) -> List[Dict[str, Any]]:
        if not self.should_append_workflow_prompt(workflow_prompt, existing_messages):
            return []
        existing = list(existing_messages or [])
        parent_message_id = str(getattr(existing[-1], "message_id", "") if existing else "")
        turn_id = str(getattr(existing[-1], "turn_id", "") if existing else "")
        step_id = str(getattr(existing[-1], "step_id", "") if existing else "")
        payloads = []
        for index, content in enumerate(list(getattr(workflow_prompt, "prompt_units", []) or [])):
            message_id = "m-" + uuid.uuid4().hex[:12]
            payloads.append(
                {
                    "role": "system",
                    "content": str(content or ""),
                    "message_id": message_id,
                    "parent_message_id": parent_message_id,
                    "turn_id": turn_id,
                    "step_id": step_id,
                    "kind": "workflow_prompt",
                    "metadata": {
                        "mode_name": str(workflow_prompt.mode_name or ""),
                        "discipline_label": str(workflow_prompt.discipline_label or ""),
                        "pack_name": str(workflow_prompt.pack_name or ""),
                        "unit_index": index,
                    },
                    "replaced_by_refs": [],
                }
            )
            parent_message_id = message_id
        return payloads

    def append_for_session(
        self,
        workflow_prompt: Any,
        session: Any,
        append_message_event: Callable[[Dict[str, Any]], None],
    ) -> bool:
        payloads = self.workflow_prompt_event_payloads(
            workflow_prompt,
            getattr(session, "messages", []),
        )
        for payload in payloads:
            append_message_event(payload)
        return bool(payloads)

    def append_described_workflow_prompt(
        self,
        extension_host: Any,
        session: Any,
        current_mode: str,
        workflow_state: str,
        append_message_event: Callable[[Dict[str, Any]], None],
        user_text: str = "",
        force: bool = False,
    ) -> bool:
        if not force and not extension_host.should_inject_workflow(user_text, current_mode):
            return False
        workflow_prompt = extension_host.describe_prompt(
            current_mode,
            workflow_state=workflow_state,
            session=session,
        )
        return self.append_for_session(workflow_prompt, session, append_message_event)
