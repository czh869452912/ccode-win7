"""Tests for strategy modules extracted from QueryEngine."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from embedagent.llm import ModelClientError
from embedagent.session import AssistantReply
from embedagent.strategies.context_compaction_engine import ContextCompactionEngine
from embedagent.strategies.llm_retry_wrapper import LLMClientRetryWrapper


class TestContextCompactionEngine(unittest.TestCase):
    def _make_engine(self, max_tokens=8000, reserve_tokens=1000):
        context_manager = MagicMock()
        return ContextCompactionEngine(
            context_manager=context_manager,
            max_tokens=max_tokens,
            reserve_tokens=reserve_tokens,
        )

    def _make_messages(self, count, chars_per_msg=4000):
        """Generate messages with known character counts."""
        messages = [{"role": "system", "content": "x" * chars_per_msg}]
        for i in range(count - 1):
            messages.append({"role": "user", "content": "y" * chars_per_msg})
        return messages

    def test_compact_reduces_over_budget(self):
        engine = self._make_engine(max_tokens=8000)
        # 5 messages * 4000 chars = 20000 chars / 4 = ~5000 tokens... wait
        # Need messages that exceed 8000 tokens
        # 8000 tokens * 4 chars/token = 32000 chars
        # Let's use 10 messages of 4000 chars = 40000 chars / 4 = 10000 tokens
        messages = self._make_messages(10, chars_per_msg=4000)
        result = engine.compact(messages)

        estimated_after = engine._estimate_tokens(result)
        self.assertLessEqual(
            estimated_after,
            8000,
            "Compacted messages should be under token budget",
        )
        # System message should be preserved
        self.assertEqual(result[0]["role"], "system")

    def test_compact_noop_under_budget(self):
        engine = self._make_engine(max_tokens=8000)
        messages = self._make_messages(2, chars_per_msg=4000)
        # 2 * 4000 = 8000 chars / 4 = 2000 tokens, well under budget

        result = engine.compact(messages)

        self.assertEqual(len(result), len(messages))
        self.assertEqual(result, messages)

    def test_estimate_tokens_approximation(self):
        engine = self._make_engine()
        messages = [
            {"role": "user", "content": "a" * 4000},
            {"role": "assistant", "content": "b" * 4000},
        ]
        # 8000 chars / 4 = 2000 tokens
        self.assertEqual(engine._estimate_tokens(messages), 2000)

        messages = [{"role": "user", "content": "x" * 100}]
        # 100 chars / 4 = 25 tokens
        self.assertEqual(engine._estimate_tokens(messages), 25)

    def test_compact_preserves_system_message(self):
        engine = self._make_engine(max_tokens=100)
        messages = [
            {"role": "system", "content": "important system prompt"},
            {"role": "user", "content": "a" * 1000},
            {"role": "user", "content": "b" * 1000},
        ]
        result = engine.compact(messages)

        self.assertEqual(result[0]["role"], "system")
        self.assertEqual(result[0]["content"], "important system prompt")

    def test_compact_by_truncation_removes_oldest(self):
        engine = self._make_engine(max_tokens=100)
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "first" * 100},
            {"role": "user", "content": "second" * 100},
            {"role": "user", "content": "third" * 100},
        ]
        result = engine.compact(messages)

        self.assertEqual(result[0]["role"], "system")
        # Should have dropped some oldest messages to get under budget
        self.assertLess(len(result), len(messages))


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
