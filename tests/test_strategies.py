"""Tests for strategy modules extracted from QueryEngine."""

from __future__ import annotations

import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from embedagent.llm import ModelClientError
from embedagent.session import Action, AssistantReply
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper


class TestLLMClientRetryWrapper(unittest.TestCase):
    def _make_wrapper(self, client=None, max_retries=3, base_delay=0.0, compaction_engine=None):
        return LLMClientRetryWrapper(
            client=client or MagicMock(),
            max_retries=max_retries,
            base_delay=base_delay,
            compaction_engine=compaction_engine,
        )

    def test_call_succeeds_first_try(self):
        client = MagicMock()
        expected_reply = AssistantReply(content="hello", actions=[])
        client.generate.return_value = expected_reply

        wrapper = self._make_wrapper(client=client)
        result = wrapper.call_with_retry(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            stream=False,
        )

        self.assertEqual(result, expected_reply)
        client.generate.assert_called_once()

    def test_retry_on_server_error(self):
        client = MagicMock()
        expected_reply = AssistantReply(content="hello", actions=[])
        client.generate.side_effect = [
            ModelClientError("HTTP 500: internal server error"),
            ModelClientError("HTTP 502: bad gateway"),
            expected_reply,
        ]

        wrapper = self._make_wrapper(client=client, base_delay=0.0)
        result = wrapper.call_with_retry(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            stream=False,
        )

        self.assertEqual(result, expected_reply)
        self.assertEqual(client.generate.call_count, 3)

    def test_context_compaction_triggered(self):
        client = MagicMock()
        compaction_engine = MagicMock()
        compacted_messages = [{"role": "system", "content": "system"}]
        compaction_engine.compact.return_value = compacted_messages
        expected_reply = AssistantReply(content="compacted", actions=[])
        client.generate.side_effect = [
            ModelClientError("context length exceeded"),
            expected_reply,
        ]

        wrapper = self._make_wrapper(
            client=client,
            base_delay=0.0,
            compaction_engine=compaction_engine,
        )
        result = wrapper.call_with_retry(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            stream=False,
        )

        self.assertEqual(result, expected_reply)
        compaction_engine.compact.assert_called_once()
        self.assertEqual(client.generate.call_count, 2)
        # Second call should use compacted messages
        call_args = client.generate.call_args_list[1]
        self.assertEqual(call_args[0][0], compacted_messages)

    def test_max_retries_exhausted(self):
        client = MagicMock()
        client.generate.side_effect = ModelClientError("HTTP 500: internal server error")

        wrapper = self._make_wrapper(client=client, max_retries=3, base_delay=0.0)
        with self.assertRaises(ModelClientError):
            wrapper.call_with_retry(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                stream=False,
            )

        self.assertEqual(client.generate.call_count, 3)

    def test_stream_mode_succeeds_first_try(self):
        client = MagicMock()
        expected_reply = AssistantReply(content="streamed", actions=[])
        client.stream.return_value = expected_reply

        wrapper = self._make_wrapper(client=client)
        result = wrapper.call_with_retry(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            stream=True,
        )

        self.assertEqual(result, expected_reply)
        client.stream.assert_called_once()

    def test_non_retryable_error_raises_immediately(self):
        client = MagicMock()
        client.generate.side_effect = ModelClientError("HTTP 400: bad request")

        wrapper = self._make_wrapper(client=client, base_delay=0.0)
        with self.assertRaises(ModelClientError):
            wrapper.call_with_retry(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                stream=False,
            )

        client.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
