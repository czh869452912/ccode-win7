from __future__ import annotations

import uuid
from typing import Any, Dict, List


class DeterministicCompactor(object):
    def build_checkpoint_payload(
        self,
        boundary_id: str,
        summary_text: str,
        created_at: str,
        first_kept_message_id: str,
        trigger: str,
        phase: str,
        token_counts: Dict[str, int],
        message_counts: Dict[str, int],
        file_activity: Dict[str, List[str]],
        evidence_refs: List[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        checkpoint_id = "ch-" + uuid.uuid4().hex[:12]
        replacement_message = {
            "role": "system",
            "content": "Compacted history summary:\n%s" % str(summary_text or ""),
            "kind": "compacted_history_summary",
            "metadata": {
                "checkpoint_id": checkpoint_id,
                "boundary_id": str(boundary_id or ""),
            },
        }
        return {
            "checkpoint_id": checkpoint_id,
            "boundary_id": str(boundary_id or ""),
            "summary_text": str(summary_text or ""),
            "first_kept_message_id": str(first_kept_message_id or ""),
            "replacement_messages": [replacement_message],
            "trigger": str(trigger or ""),
            "phase": str(phase or ""),
            "token_counts": dict(token_counts or {}),
            "message_counts": dict(message_counts or {}),
            "file_activity": dict(file_activity or {}),
            "evidence_refs": list(evidence_refs or []),
            "extension_summary": False,
            "created_at": str(created_at or ""),
            "metadata": dict(metadata or {}),
        }
