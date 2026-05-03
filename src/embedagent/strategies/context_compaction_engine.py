"""Context compaction engine for enforcing token budgets.

Extracted from QueryEngine to separate context management concerns.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

_LOG = logging.getLogger(__name__)


class ContextCompactionEngine(object):
    """Enforces token budgets on message lists via truncation or summarization."""

    def __init__(
        self,
        context_manager: Any,
        max_tokens: int = 8000,
        reserve_tokens: int = 1000,
    ) -> None:
        self.context_manager = context_manager
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.effective_budget = max(0, max_tokens - reserve_tokens)

    def compact(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return a message list that fits within the token budget.

        Priority order: system message (never drop) > recent turns > old turns.
        """
        current_tokens = self._estimate_tokens(messages)
        if current_tokens <= self.effective_budget:
            return messages

        before_count = len(messages)

        # Try truncation first
        result = self._compact_by_truncation(messages, self.effective_budget)
        after_count = len(result)

        _LOG.info(
            "Compacted %d -> %d messages (~%d tokens)",
            before_count,
            after_count,
            self._estimate_tokens(result),
        )
        return result

    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Rough token estimation: ~4 characters per token."""
        total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
        return total_chars // 4

    def _compact_by_truncation(
        self,
        messages: List[Dict[str, Any]],
        target_tokens: int,
    ) -> List[Dict[str, Any]]:
        """Remove oldest messages (after system) until under budget."""
        if not messages:
            return messages

        # Keep system message at index 0 if present
        if messages[0].get("role") == "system":
            head = [messages[0]]
            tail = messages[1:]
        else:
            head = []
            tail = messages[:]

        # If even the head exceeds budget, just return head
        if self._estimate_tokens(head) > target_tokens:
            return head

        # Greedily keep newest messages from tail
        remaining_budget = target_tokens - self._estimate_tokens(head)
        kept_tail = []
        # Walk backwards to keep newest
        for msg in reversed(tail):
            msg_tokens = self._estimate_tokens([msg])
            if msg_tokens <= remaining_budget:
                kept_tail.insert(0, msg)
                remaining_budget -= msg_tokens
            else:
                break

        result = head + kept_tail
        return result
