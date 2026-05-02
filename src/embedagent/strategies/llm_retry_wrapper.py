"""LLM client retry wrapper with backoff and context-compaction fallback.

Extracted from QueryEngine to separate retry and backoff concerns.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional

from embedagent.llm import ModelClientError, OpenAICompatibleClient
from embedagent.session import AssistantReply

_LOG = logging.getLogger(__name__)

_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0
_COMPACT_RETRY_ERROR_MARKERS = (
    "context length",
    "maximum context",
    "prompt is too long",
    "prompt too long",
    "max tokens",
    "too many tokens",
    "上下文",
    "超出上下文",
)


class LLMClientRetryWrapper(object):
    """Wraps LLM calls with retry logic and optional context compaction."""

    def __init__(
        self,
        client: OpenAICompatibleClient,
        max_retries: int = _LLM_MAX_RETRIES,
        base_delay: float = _LLM_RETRY_BASE_DELAY,
        compaction_engine: Optional[Any] = None,
    ) -> None:
        self.client = client
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.compaction_engine = compaction_engine

    def call_with_retry(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        stream: bool = False,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_reasoning_delta: Optional[Callable[[str], None]] = None,
    ) -> AssistantReply:
        """Call LLM with retry and optional context compaction.

        Retries on retryable HTTP errors with exponential backoff.
        On context-length errors, compacts messages (if engine available) and retries once.
        """
        last_exc: Optional[Exception] = None
        compact_retry_used = False
        current_messages = messages

        for attempt in range(self.max_retries):
            try:
                if stream:
                    return self.client.stream(
                        current_messages,
                        tools=tools,
                        on_text_delta=on_text_delta,
                        on_reasoning_delta=on_reasoning_delta,
                    )
                reply = self.client.generate(current_messages, tools=tools)
                if on_reasoning_delta and reply.reasoning_content:
                    on_reasoning_delta(reply.reasoning_content)
                if on_text_delta and reply.content:
                    on_text_delta(reply.content)
                return reply
            except ModelClientError as exc:
                last_exc = exc
                error_text = str(exc).lower()

                # Check for context-length error first
                if (
                    self._is_context_length_error(error_text)
                    and not compact_retry_used
                    and self.compaction_engine is not None
                ):
                    _LOG.warning(
                        "LLM context-length error detected; compacting and retrying"
                    )
                    current_messages = self.compaction_engine.compact(current_messages)
                    compact_retry_used = True
                    continue

                if not self._should_retry_on_error(exc):
                    raise

                if attempt >= self.max_retries - 1:
                    raise

                delay = self.base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                _LOG.warning(
                    "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    self.max_retries,
                    delay,
                    exc,
                )
                time.sleep(delay)

        if last_exc is not None:
            raise last_exc
        # This should never be reached, but satisfies type checker
        raise RuntimeError("Unexpected state: exhausted retry loop without exception")

    def _should_retry_on_error(self, error: Exception) -> bool:
        """Return True if the error indicates a retryable HTTP condition."""
        error_text = str(error)
        return any(str(code) in error_text for code in _RETRYABLE_HTTP_CODES)

    def _is_context_length_error(self, error_message: str) -> bool:
        """Return True if the error message indicates a context-length issue."""
        if not error_message:
            return False
        for marker in _COMPACT_RETRY_ERROR_MARKERS:
            if marker in error_message:
                return True
        return False
