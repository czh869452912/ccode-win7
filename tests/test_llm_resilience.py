"""Tests for LLM retry streaming and token tracking."""

import unittest
from unittest.mock import Mock

from embedagent_core.session import AssistantReply
from embedagent_core.strategies.llm_retry_wrapper import LLMClientRetryWrapper
from embedagent_host.providers.openai_compatible import OpenAICompatibleClient


class TestLLMResilienceIntegration(unittest.TestCase):
    def test_token_tracking_on_success(self):
        mock_client = Mock()
        mock_client.generate.return_value = AssistantReply(
            content="hello",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        tokens = []

        def tracker(p, c, t):
            tokens.append((p, c, t))

        wrapper = LLMClientRetryWrapper(mock_client, token_tracker=tracker)

        reply = wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])
        self.assertEqual(reply.content, "hello")
        self.assertEqual(tokens, [(10, 5, 15)])

    def test_token_tracking_zero_when_no_usage(self):
        mock_client = Mock()
        mock_client.generate.return_value = AssistantReply(
            content="hello",
            usage={},
        )

        tokens = []

        def tracker(p, c, t):
            tokens.append((p, c, t))

        wrapper = LLMClientRetryWrapper(mock_client, token_tracker=tracker)

        wrapper.call_with_retry([{"role": "user", "content": "hi"}], [])
        self.assertEqual(tokens, [(0, 0, 0)])

    def test_streaming_does_not_replay_final_content_delta(self):
        mock_client = Mock()

        def stream(messages, tools, on_text_delta=None, on_reasoning_delta=None):
            if on_text_delta is not None:
                on_text_delta("hello")
            return AssistantReply(content="hello", finish_reason="stop")

        mock_client.stream.side_effect = stream
        wrapper = LLMClientRetryWrapper(mock_client)
        deltas = []

        reply = wrapper.call_with_retry(
            [{"role": "user", "content": "hi"}],
            [],
            stream=True,
            on_text_delta=deltas.append,
        )

        self.assertEqual(reply.content, "hello")
        self.assertEqual(deltas, ["hello"])

    def test_non_streaming_can_emit_final_content_delta(self):
        mock_client = Mock()
        mock_client.generate.return_value = AssistantReply(content="hello", finish_reason="stop")
        wrapper = LLMClientRetryWrapper(mock_client)
        deltas = []

        reply = wrapper.call_with_retry(
            [{"role": "user", "content": "hi"}],
            [],
            stream=False,
            on_text_delta=deltas.append,
        )

        self.assertEqual(reply.content, "hello")
        self.assertEqual(deltas, ["hello"])


class _FakeSseResponse(object):
    def __init__(self, lines):
        self._lines = lines

    def __iter__(self):
        for line in self._lines:
            yield line.encode("utf-8")


class TestOpenAICompatibleStreamingUsage(unittest.TestCase):
    def _client(self):
        return OpenAICompatibleClient(
            base_url="http://127.0.0.1:8000/v1",
            api_key="",
            model="local-test",
        )

    def test_streaming_without_provider_usage_does_not_fabricate_total_tokens(self):
        client = self._client()
        response = _FakeSseResponse(
            [
                'data: {"choices":[{"delta":{"content":"hello"},"finish_reason":null}]}\n',
                "\n",
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n',
                "\n",
                "data: [DONE]\n",
                "\n",
            ]
        )

        reply = client._parse_stream_response(response, on_text_delta=None, on_reasoning_delta=None)

        self.assertEqual(reply.content, "hello")
        self.assertEqual(reply.usage, {})

    def test_streaming_uses_real_provider_usage_from_sse_chunk(self):
        client = self._client()
        response = _FakeSseResponse(
            [
                'data: {"choices":[{"delta":{"content":"hello"},"finish_reason":null}]}\n',
                "\n",
                (
                    'data: {"usage":{"prompt_tokens":10,"completion_tokens":2,'
                    '"total_tokens":12},"choices":[{"delta":{},"finish_reason":"stop"}]}\n'
                ),
                "\n",
                "data: [DONE]\n",
                "\n",
            ]
        )

        reply = client._parse_stream_response(response, on_text_delta=None, on_reasoning_delta=None)

        self.assertEqual(
            reply.usage, {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
        )


if __name__ == "__main__":
    unittest.main()
