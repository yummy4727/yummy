"""llm：服务商预设、OpenAI/Anthropic 双协议、连接自检。"""

from __future__ import annotations

import json

import httpx
import pytest

from paotuan.llm import LLMClient, LLMError, friendly_error
from paotuan.llm.presets import CUSTOM_ID, PROVIDER_MAP, PROVIDERS, detect_provider


def _client(handler, **kw):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    defaults = dict(api_key="sk-test", model="test-model", api_style="openai")
    defaults.update(kw)
    return LLMClient(base_url="https://mock.test/v1", http=http, **defaults)


# ------------------------------------------------------------- 服务商注册表


def test_presets_registry():
    for pid in (
        "deepseek",
        "opencode",
        "opencode-go",
        "openai",
        "kimi",
        "zhipu",
        "qwen",
        "siliconflow",
        "openrouter",
        "anthropic",
        "gemini",
        CUSTOM_ID,
    ):
        assert pid in PROVIDER_MAP
    for p in PROVIDERS:
        assert p.name
        assert p.id == CUSTOM_ID or p.base_url
    assert PROVIDER_MAP["anthropic"].api_style == "anthropic"
    assert PROVIDER_MAP["deepseek"].api_style == "openai"
    assert PROVIDER_MAP["deepseek"].models


def test_siliconflow_covers_current_models():
    ids = {m.id for m in PROVIDER_MAP["siliconflow"].models}
    assert "deepseek-ai/DeepSeek-V4-Pro" in ids
    assert "deepseek-ai/DeepSeek-V4-Flash" in ids
    assert "deepseek-ai/DeepSeek-V3.2" in ids
    assert "zai-org/GLM-5.2" in ids
    assert "Qwen/Qwen3.6-35B-A3B" in ids
    assert "Qwen/Qwen3.5-397B-A17B" in ids
    assert "moonshotai/Kimi-K2.7-Code" in ids
    assert "Pro/moonshotai/Kimi-K2.6" in ids
    assert "MiniMaxAI/MiniMax-M2.5" in ids
    assert "nex-agi/Nex-N2-Pro" in ids


def test_detect_provider():
    assert detect_provider("https://api.openai.com/v1") == "openai"
    assert detect_provider("https://api.deepseek.com") == "deepseek"
    assert detect_provider("https://example.com/custom") is None
    assert detect_provider("") is None


# ------------------------------------------------------------- OpenAI 协议


def test_openai_generate_text():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("Authorization")
        seen["body"] = json.loads(req.read())
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好"}}]})

    c = _client(handler)
    assert c.generate_text([{"role": "user", "content": "hi"}]) == "你好"
    assert seen["url"].endswith("/chat/completions")
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["model"] == "test-model"
    assert seen["body"]["stream"] is False
    assert seen["body"]["temperature"] == 0.8


def test_openai_generate_json_strips_fences():
    def handler(req):
        body = json.loads(req.read())
        assert body.get("response_format") == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]},
        )

    c = _client(handler)
    assert c.generate_json([{"role": "user", "content": "x"}]) == {"a": 1}


# ------------------------------------------------------------- Anthropic 协议


def test_anthropic_generate_text_system_field():
    seen = {}

    def handler(req):
        seen["headers"] = req.headers
        seen["body"] = json.loads(req.read())
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "嗨"}]},
        )

    c = _client(handler, api_style="anthropic")
    out = c.generate_text(
        [
            {"role": "system", "content": "你是旁白"},
            {"role": "user", "content": "你好"},
        ]
    )
    assert out == "嗨"
    assert seen["body"]["system"] == "你是旁白"
    assert seen["body"]["messages"] == [{"role": "user", "content": "你好"}]
    assert seen["body"]["max_tokens"] > 0
    assert seen["headers"]["x-api-key"] == "sk-test"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"


# ------------------------------------------------------------- 连接自检


def test_ping_success():
    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": "pong"}}]})

    ok, msg = _client(handler).ping()
    assert ok
    assert "pong" in msg


def test_ping_thinking_model_reasoning_only():
    def handler(req):
        body = json.loads(req.read())
        assert body["max_tokens"] >= 256
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": "思考中…pong",
                        }
                    }
                ]
            },
        )

    ok, msg = _client(handler).ping()
    assert ok
    assert "pong" in msg


def test_ping_still_empty_when_neither_content():
    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    ok, msg = _client(handler).ping()
    assert not ok
    assert "空回复" in msg


@pytest.mark.parametrize(
    ("status", "needle"),
    [
        (401, "API Key"),
        (403, "API Key"),
        (404, "Base URL"),
        (429, "频繁"),
        (400, "模型"),
    ],
)
def test_ping_error_hints(status, needle):
    def handler(req):
        return httpx.Response(status, text="error")

    ok, msg = _client(handler).ping()
    assert not ok
    assert needle in msg


def test_ping_network_error_hint():
    def handler(req):
        raise httpx.ConnectError("boom")

    ok, msg = _client(handler).ping()
    assert not ok
    assert "网络" in msg


def test_friendly_error_unknown():
    exc = LLMError("服务器内部错误", status_code=500)
    assert "500" in friendly_error(exc)
