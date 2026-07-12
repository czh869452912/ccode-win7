from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ContextUsageEstimate:
    tokens: Optional[int]
    source: str
    usage_tokens: int = 0
    trailing_estimate_tokens: int = 0
    last_usage_message_id: str = ""
    context_window: int = 0
    threshold_tokens: int = 0
    percent: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens": self.tokens,
            "source": self.source,
            "usage_tokens": self.usage_tokens,
            "trailing_estimate_tokens": self.trailing_estimate_tokens,
            "last_usage_message_id": self.last_usage_message_id,
            "context_window": self.context_window,
            "threshold_tokens": self.threshold_tokens,
            "percent": self.percent,
        }


class ContextUsageEstimator(object):
    def __init__(self, chars_per_token: float = 3.0) -> None:
        self.chars_per_token = chars_per_token if chars_per_token > 0 else 1.0

    def estimate_session(
        self,
        session: Any,
        context_window: int = 0,
        reserve_tokens: int = 0,
    ) -> ContextUsageEstimate:
        messages = list(getattr(session, "messages", []) or [])
        threshold = max(0, int(context_window or 0) - int(reserve_tokens or 0))
        boundary = (
            session.latest_compact_boundary()
            if hasattr(session, "latest_compact_boundary")
            else None
        )
        first_allowed_index = self._first_allowed_usage_index(messages, boundary)
        latest_usage_index = -1
        latest_usage_tokens = 0
        latest_usage_message_id = ""

        for index in range(len(messages) - 1, -1, -1):
            if index < first_allowed_index:
                break
            message = messages[index]
            if getattr(message, "role", "") != "assistant":
                continue
            metadata = dict(getattr(message, "metadata", {}) or {})
            finish_reason = str(metadata.get("finish_reason") or "").strip().lower()
            if finish_reason in ("aborted", "error"):
                continue
            usage = metadata.get("usage") or {}
            usage_tokens = self._usage_tokens(dict(usage or {}))
            if usage_tokens <= 0:
                continue
            latest_usage_index = index
            latest_usage_tokens = usage_tokens
            latest_usage_message_id = str(getattr(message, "message_id", "") or "")
            break

        if latest_usage_index < 0:
            if boundary is not None:
                return ContextUsageEstimate(
                    tokens=None,
                    source="unknown_after_compaction",
                    context_window=int(context_window or 0),
                    threshold_tokens=threshold,
                    percent=None,
                )
            estimated = self._estimate_messages(messages)
            return ContextUsageEstimate(
                tokens=estimated,
                source="estimate",
                usage_tokens=0,
                trailing_estimate_tokens=estimated,
                context_window=int(context_window or 0),
                threshold_tokens=threshold,
                percent=self._percent(estimated, context_window),
            )

        trailing = self._estimate_messages(messages[latest_usage_index + 1 :])
        total = latest_usage_tokens + trailing
        return ContextUsageEstimate(
            tokens=total,
            source="provider_usage" if trailing == 0 else "provider_usage_plus_estimate",
            usage_tokens=latest_usage_tokens,
            trailing_estimate_tokens=trailing,
            last_usage_message_id=latest_usage_message_id,
            context_window=int(context_window or 0),
            threshold_tokens=threshold,
            percent=self._percent(total, context_window),
        )

    def _usage_tokens(self, usage: Dict[str, Any]) -> int:
        total = int(usage.get("total_tokens") or 0)
        if total > 0:
            return total
        return int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)

    def _first_allowed_usage_index(self, messages: Any, boundary: Any) -> int:
        if boundary is None:
            return 0
        tail_id = str(getattr(boundary, "preserved_tail_message_id", "") or "")
        if tail_id:
            for index, message in enumerate(messages):
                if str(getattr(message, "message_id", "") or "") == tail_id:
                    return index + 1
        return len(messages)

    def _estimate_messages(self, messages: Any) -> int:
        chars = 0
        for message in list(messages or []):
            payload = message.to_api_dict() if hasattr(message, "to_api_dict") else message
            chars += len(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return int(math.ceil(float(chars) / self.chars_per_token))

    def _percent(self, tokens: int, context_window: int) -> Optional[float]:
        window = int(context_window or 0)
        if window <= 0:
            return None
        return (float(tokens) / float(window)) * 100.0
