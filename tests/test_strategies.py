"""Tests for strategy modules extracted from QueryEngine."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from embedagent.llm import ModelClientError
from embedagent_core.session import AssistantReply
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper


class TestLLMClientRetryWrapper(unittest.TestCase):
    def _make_wrapper(self, client=None, max_retries=3, base_delay=0.0):
        return LLMClientRetryWrapper(
            client=client or MagicMock(),
            max_retries=max_retries,
            base_delay=base_delay,
        )

    def test_constructor_rejects_wrapper_level_compaction_engine(self):
        with self.assertRaises(TypeError):
            LLMClientRetryWrapper(
                client=MagicMock(),
                compaction_engine=MagicMock(),
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

    def test_context_length_error_raises_without_wrapper_level_compaction(self):
        client = MagicMock()
        client.generate.side_effect = ModelClientError("context length exceeded")

        wrapper = self._make_wrapper(client=client, base_delay=0.0)

        with self.assertRaises(ModelClientError):
            wrapper.call_with_retry(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                stream=False,
            )
        client.generate.assert_called_once()

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
