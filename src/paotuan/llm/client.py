"""LLM 客户端：OpenAI 兼容 / Anthropic Messages 双协议，httpx 同步。

- STYLE_OPENAI：POST {base_url}/chat/completions，Authorization: Bearer
- STYLE_ANTHROPIC：POST {base_url}/v1/messages，x-api-key（system 单独成字段）
"""

from __future__ import annotations

import json
import re
from typing import Any, Sequence

import httpx

from .presets import STYLE_ANTHROPIC, STYLE_OPENAI

DEFAULT_MAX_TOKENS = 4096

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.8,
        timeout: float = 60.0,
        api_style: str = STYLE_OPENAI,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        extra_headers: Sequence[tuple[str, str]] = (),
        http: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.api_style = api_style
        self.max_tokens = max_tokens
        self.extra_headers = list(extra_headers)
        self._http = http or httpx.Client(timeout=timeout)

    # ---------------------------------------------------------------- 请求装配
    def _headers(self) -> dict[str, str]:
        if self.api_style == "anthropic":
            headers: dict[str, str] = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            }
        else:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
        for k, v in self.extra_headers:
            headers[k] = v
        return headers

    def _endpoint(self) -> str:
        if self.api_style == "anthropic":
            return f"{self.base_url}/v1/messages"
        return f"{self.base_url}/chat/completions"

    @staticmethod
    def _split_system(
        messages: Sequence[dict[str, str]],
    ) -> tuple[str, list[dict[str, str]]]:
        """把开头的 system 消息抽出为单独字符串（Anthropic 协议）。"""
        system_parts: list[str] = []
        rest: list[dict[str, str]] = []
        for m in messages:
            if m.get("role") == "system":
                system_parts.append(str(m.get("content", "")))
            else:
                rest.append(
                    {"role": m["role"], "content": str(m.get("content", ""))}
                )
        return "\n\n".join(p for p in system_parts if p), rest

    def _build_payload(self, messages: Sequence[dict[str, str]], json_mode: bool) -> dict:
        if self.api_style == "anthropic":
            system, msgs = self._split_system(messages)
            payload: dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": msgs,
            }
            if system:
                payload["system"] = system
        else:
            payload = {
                "model": self.model,
                "messages": list(messages),
                "temperature": self.temperature,
                "stream": False,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _extract_content(data: dict) -> str:
        try:
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            if not content.strip():
                # 思考模型可能只返回 reasoning_content，正文尚未产出
                content = msg.get("reasoning_content") or ""
            return content
        except (KeyError, IndexError, TypeError):
            pass
        try:
            parts = data["content"]
            if isinstance(parts, list):
                return "".join(
                    p.get("text", "") for p in parts if p.get("type") == "text"
                )
        except (KeyError, TypeError):
            pass
        raise LLMError(f"响应格式异常: {str(data)[:300]}")

    @staticmethod
    def _parse_json(content: str) -> dict:
        cleaned = _FENCE_RE.sub("", content.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM 未返回合法 JSON: {content[:200]!r}") from exc

    # ---------------------------------------------------------------- 对外接口
    def generate_text(self, messages: Sequence[dict[str, str]]) -> str:
        """普通文本生成。messages: [{"role": ..., "content": ...}, ...]。"""
        data = self._post(self._build_payload(messages, json_mode=False))
        return self._extract_content(data)

    def generate_json(self, messages: Sequence[dict[str, str]]) -> dict:
        """JSON 模式输出（M2 意图拆解用）。"""
        data = self._post(self._build_payload(messages, json_mode=True))
        content = self._extract_content(data)
        return self._parse_json(content)

    def ping(self, prompt: str = "请只回复两个字符：pong") -> tuple[bool, str]:
        """连接自检：发一条最小请求验证 Key / 地址 / 模型是否可用。"""
        messages = [{"role": "user", "content": prompt}]
        if self.api_style == "anthropic":
            payload: dict[str, Any] = {
                "model": self.model,
                "max_tokens": 256,
                "temperature": 0.0,
                "messages": messages,
            }
        else:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 256,
                "stream": False,
            }
        try:
            data = self._post(payload)
            text = self._extract_content(data).strip()
        except LLMError as exc:
            return False, friendly_error(exc)
        if not text:
            return False, "服务返回了空回复"
        return True, f"连接成功，模型回复：{text[:50]}"

    def _post(self, payload: dict) -> dict:
        try:
            resp = self._http.post(self._endpoint(), headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"网络错误: {exc}") from exc
        if resp.status_code != 200:
            raise LLMError(
                f"HTTP {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise LLMError("响应不是合法 JSON") from exc

    def close(self) -> None:
        self._http.close()


def friendly_error(exc: LLMError) -> str:
    """把 LLMError 翻译成用户能看懂的提示。"""
    sc = getattr(exc, "status_code", None)
    if sc in (401, 403):
        return "API Key 无效或没有权限，请检查后重试。"
    if sc == 404:
        return "接口地址或模型不存在，请检查 Base URL 与模型名。"
    if sc == 429:
        return "请求过于频繁或额度不足，请稍后再试。免费档模型限速较严，可稍候重试或换用付费模型。"
    if sc == 400:
        return "请求参数错误（模型名可能不正确）。"
    if sc is None and "网络错误" in str(exc):
        return "网络或连接失败，请检查网络/代理后重试。"
    if sc:
        return f"服务返回错误：HTTP {sc} - {exc}"
    return f"服务返回错误：{exc}"
