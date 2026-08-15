"""可选外部审查 API（M2）：OpenAI Moderation 兼容接口。

默认对接 OpenAI Moderation（`POST {base_url}/moderations`，`{input, model}`），
也兼容任何实现同一接口的代理（百度 AI 内容审核等可自行做适配层指向此端点）。

失败策略：
- 命中违规 → `check()` 返回 True；
- API 调用本身出错（网络/鉴权）→ 记录日志并**放行**（fail-open），
  避免可选审查服务不可用时阻塞游戏；本地敏感词仍是最先拦截的一道闸。
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "text-moderation-latest"


class RemoteCensor:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        enabled: bool = True,
        model: str = DEFAULT_MODEL,
        timeout: float = 10.0,
        http: httpx.Client | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.enabled = enabled
        self.model = model
        self.timeout = timeout
        self._http = http or httpx.Client(timeout=timeout)

    def check(self, text: str) -> bool:
        """返回 True 表示违规。API 出错时放行（fail-open）并记录日志。"""
        if not self.enabled or not self.api_key:
            return False
        try:
            resp = self._http.post(
                f"{self.base_url}/moderations",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json={"input": text, "model": self.model},
            )
        except httpx.HTTPError as exc:
            logger.warning("远程审查请求失败（放行）: %s", exc)
            return False
        if resp.status_code != 200:
            logger.warning("远程审查返回 HTTP %s（放行）: %s", resp.status_code, resp.text[:200])
            return False
        try:
            results = resp.json().get("results") or []
        except ValueError:
            logger.warning("远程审查响应非 JSON（放行）")
            return False
        return bool(results and results[0].get("flagged"))

    def close(self) -> None:
        self._http.close()


class CompositeCensor:
    """本地敏感词 + 可选远程审查的组合审查器（任一命中即违规）。"""

    def __init__(self, local, remote: RemoteCensor | None = None):
        self.local = local
        self.remote = remote

    def check(self, text: str) -> bool:
        if self.local.check(text):
            return True
        if self.remote is not None and self.remote.check(text):
            return True
        return False