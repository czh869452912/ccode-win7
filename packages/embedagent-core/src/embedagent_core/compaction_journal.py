from __future__ import annotations

from typing import Any, Dict, List

from embedagent_core.compactor import DeterministicCompactor
from embedagent_core.context_window import ContextWindowState
from embedagent_core.session import CompactBoundary, ContextAssemblyResult


class CompactionJournal(object):
    """Builds durable compaction event payloads without mutating session state."""

    def __init__(self, compactor: DeterministicCompactor = None) -> None:
        self._compactor = compactor or DeterministicCompactor()

    def new_boundary(
        self,
        summary_text: str,
        compacted_turn_count: int,
        mode_name: str,
        metadata: Dict[str, Any],
        preserved_head_message_id: str,
        preserved_tail_message_id: str,
    ) -> CompactBoundary:
        return CompactBoundary(
            summary_text=str(summary_text or ""),
            compacted_turn_count=max(0, int(compacted_turn_count or 0)),
            mode_name=str(mode_name or ""),
            preserved_head_message_id=str(preserved_head_message_id or ""),
            preserved_tail_message_id=str(preserved_tail_message_id or ""),
            metadata=dict(metadata or {}),
        )

    def token_counts(self, assembly: ContextAssemblyResult) -> Dict[str, int]:
        stats = getattr(assembly, "stats", None)
        return {
            "approx_before": int(getattr(stats, "approx_tokens_before", 0) or 0),
            "approx_after": int(
                getattr(stats, "approx_tokens_after", 0) or assembly.approx_tokens or 0
            ),
        }

    def message_counts(self, assembly: ContextAssemblyResult) -> Dict[str, int]:
        stats = getattr(assembly, "stats", None)
        total_messages = int(getattr(stats, "total_session_messages", 0) or 0)
        selected_messages = int(getattr(stats, "selected_messages", 0) or len(assembly.messages))
        summarized_turns = int(
            getattr(stats, "summarized_turns", 0) or assembly.summarized_turns or 0
        )
        recent_turns = int(getattr(stats, "recent_turns", 0) or assembly.recent_turns or 0)
        return {
            "before": total_messages,
            "after": selected_messages,
            "summarized_turns": summarized_turns,
            "recent_turns": recent_turns,
        }

    def file_activity(self, assembly: ContextAssemblyResult) -> Dict[str, List[str]]:
        analysis = getattr(assembly, "analysis", {}) or {}
        if not isinstance(analysis, dict):
            analysis = {}
        read_files = []
        seen = set()
        for item in list(analysis.get("top_hot_files") or []):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if not path or path in seen:
                continue
            seen.add(path)
            read_files.append(path)
        return {
            "read_files": sorted(read_files),
            "modified_files": [],
        }

    def evidence_refs(self, assembly: ContextAssemblyResult) -> List[str]:
        refs = []
        seen = set()
        for replacement in list(getattr(assembly, "replacements", []) or []):
            if not isinstance(replacement, dict):
                continue
            for item in list(replacement.get("stored_refs") or []):
                ref = str(item or "").strip()
                if not ref or ref in seen:
                    continue
                seen.add(ref)
                refs.append(ref)
        return sorted(refs)

    def boundary_payload(
        self,
        boundary: Any,
        window_state: ContextWindowState,
        token_counts: Dict[str, int],
        message_counts: Dict[str, int],
        file_activity: Dict[str, List[str]],
        evidence_refs: List[str],
    ) -> Dict[str, Any]:
        return {
            "boundary_id": boundary.boundary_id,
            "summary_text": boundary.summary_text,
            "compacted_turn_count": boundary.compacted_turn_count,
            "created_at": boundary.created_at,
            "mode_name": boundary.mode_name,
            "preserved_head_message_id": boundary.preserved_head_message_id,
            "preserved_tail_message_id": boundary.preserved_tail_message_id,
            "trigger": window_state.trigger,
            "phase": window_state.phase,
            "context_window_generation": window_state.context_window_generation,
            "metadata": dict(boundary.metadata),
            "token_counts": token_counts,
            "message_counts": message_counts,
            "file_activity": file_activity,
            "evidence_refs": evidence_refs,
            "extension_summary": False,
        }

    def compacted_history_payload(
        self,
        boundary: Any,
        assembly: ContextAssemblyResult,
        window_state: ContextWindowState,
        token_counts: Dict[str, int],
        message_counts: Dict[str, int],
        file_activity: Dict[str, List[str]],
        evidence_refs: List[str],
    ) -> Dict[str, Any]:
        return self._compactor.build_checkpoint_payload(
            boundary_id=str(getattr(boundary, "boundary_id", "") or ""),
            summary_text=str(getattr(boundary, "summary_text", "") or ""),
            created_at=str(getattr(boundary, "created_at", "") or ""),
            first_kept_message_id=str(getattr(boundary, "preserved_head_message_id", "") or ""),
            trigger=window_state.trigger,
            phase=window_state.phase,
            token_counts=token_counts,
            message_counts=message_counts,
            file_activity=file_activity,
            evidence_refs=evidence_refs,
            metadata={
                "pipeline_steps": list(getattr(assembly, "pipeline_steps", []) or []),
                "source_boundary_id": str(getattr(boundary, "boundary_id", "") or ""),
            },
        )

    def build_payloads(
        self,
        boundary: Any,
        assembly: ContextAssemblyResult,
        window_state: ContextWindowState,
        plan_payload: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        token_counts = self.token_counts(assembly)
        message_counts = self.message_counts(assembly)
        message_counts.update(dict((plan_payload or {}).get("message_counts") or {}))
        file_activity = self.file_activity(assembly)
        evidence_refs = self.evidence_refs(assembly)
        boundary_payload = self.boundary_payload(
            boundary,
            window_state,
            token_counts,
            message_counts,
            file_activity,
            evidence_refs,
        )
        history_payload = self.compacted_history_payload(
            boundary,
            assembly,
            window_state,
            token_counts,
            message_counts,
            file_activity,
            evidence_refs,
        )
        return {
            "compact_boundary": boundary_payload,
            "compacted_history": history_payload,
        }
