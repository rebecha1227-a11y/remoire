import unittest

from app.llm import ModelConfig, _anthropic_payload, _anthropic_response_message, _usage_metrics
from app.services.model_settings_service import (
    capabilities_from_model_metadata,
    infer_model_capabilities,
    resolve_model_capabilities,
)
from app.tools import select_tools


class PromptCachingTests(unittest.TestCase):
    def test_claude_opus_46_gateway_alias_uses_verified_limits(self):
        caps = infer_model_capabilities("「按量」claude-opus-4-6-渠道2")
        self.assertEqual(caps["context_window"], 1_000_000)
        self.assertEqual(caps["max_output_tokens"], 128_000)
        self.assertEqual(caps["cache_min_tokens"], 4_096)
        self.assertTrue(caps["prompt_caching"])

    def test_common_gateway_aliases_use_verified_capabilities(self):
        gemini = infer_model_capabilities("「按量」gemini-2.5-pro-vertex")
        deepseek = infer_model_capabilities("deepseek-v4-flash")
        self.assertEqual(gemini["context_window"], 1_048_576)
        self.assertEqual(gemini["max_output_tokens"], 65_536)
        self.assertEqual(deepseek["context_window"], 1_000_000)
        self.assertEqual(deepseek["max_output_tokens"], 393_216)

    def test_provider_model_metadata_is_normalized_and_caps_registry_limits(self):
        metadata = capabilities_from_model_metadata({
            "inputTokenLimit": 200_000,
            "outputTokenLimit": 20_000,
        })
        self.assertEqual(metadata["context_window"], 200_000)
        self.assertEqual(metadata["max_output_tokens"], 20_000)

        resolved = resolve_model_capabilities("claude-opus-4-6", {
            "context_window": 180_000,
            "max_output_tokens": 16_000,
        })
        self.assertEqual(resolved["context_window"], 180_000)
        self.assertEqual(resolved["max_output_tokens"], 16_000)

    def test_usage_metrics_support_anthropic_and_openai_cache_fields(self):
        anthropic = _usage_metrics({
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_creation_input_tokens": 4_000,
            "cache_read_input_tokens": 8_000,
        })
        openai = _usage_metrics({
            "prompt_tokens": 9_000,
            "completion_tokens": 30,
            "prompt_tokens_details": {"cached_tokens": 7_000},
        })
        self.assertEqual(anthropic["cache_creation_input_tokens"], 4_000)
        self.assertEqual(anthropic["cache_read_input_tokens"], 8_000)
        self.assertTrue(anthropic["cache_reported"])
        self.assertEqual(openai["cache_read_input_tokens"], 7_000)
        self.assertTrue(openai["cache_reported"])

    def test_stable_tool_catalog_does_not_change_with_chat_wording(self):
        ordinary = select_tools("抱抱我", stable=True)
        diary = select_tools("看看我们的日记", has_diary_notifications=True, stable=True)
        self.assertEqual(ordinary, diary)
        names = [item["function"]["name"] for item in ordinary]
        self.assertIn("remember", names)
        self.assertIn("search_memories", names)
        self.assertIn("write_diary", names)
        self.assertIn("web_search", names)

    def test_anthropic_request_marks_only_stable_system_prefix(self):
        config = ModelConfig(
            "https://gateway.example/v1",
            "secret",
            "claude-opus-4-6",
        )
        payload = _anthropic_payload(
            config,
            [
                {
                    "role": "system",
                    "content": "固定身份与表达",
                    "cache_control": {"type": "ephemeral"},
                },
                {"role": "system", "content": "动态时间与记忆"},
                {"role": "user", "content": "今天好吗"},
            ],
            stream=False,
            temperature=0.9,
            max_tokens=128_000,
            tools=[{
                "type": "function",
                "function": {
                    "name": "remember",
                    "description": "记住",
                    "parameters": {"type": "object", "properties": {}},
                },
            }],
            extended_thinking=True,
        )
        self.assertEqual(payload["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", payload["system"][1])
        self.assertEqual(payload["thinking"], {"type": "adaptive"})
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["tools"][0]["input_schema"]["type"], "object")

    def test_anthropic_tool_response_keeps_thinking_signature_for_next_round(self):
        raw_blocks = [
            {"type": "thinking", "thinking": "先找记忆", "signature": "signed"},
            {"type": "tool_use", "id": "tool-1", "name": "search_memories", "input": {"q": "海边"}},
        ]
        message = _anthropic_response_message({
            "content": raw_blocks,
            "stop_reason": "tool_use",
            "usage": {"cache_read_input_tokens": 5000},
        })
        self.assertEqual(message["_finish_reason"], "tool_calls")
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "search_memories")
        self.assertEqual(message["_anthropic_content"], raw_blocks)


if __name__ == "__main__":
    unittest.main()
