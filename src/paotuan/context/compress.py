"""记忆压缩（M2）：当历史过长时，用 LLM 把较早对话摘要，替代原始文本。

压缩后 `History.summary` 写入摘要，`History.messages` 只保留最近若干条；
`History.as_list()` 会把摘要作为首条 system 消息注入，保证模型仍有完整前情。

压缩失败（LLM 异常/超长）时保持原历史不变并放行，绝不阻塞正文生成。
"""

from __future__ import annotations

import logging

from paotuan.llm import LLMClient

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = """你正在压缩一段互动叙事的对话历史。请用第三人称、简洁的中文，把下面的历史
浓缩为一段【剧情回顾】摘要（不超过 400 字），保留：发生了哪些关键事件、玩家做过的
重要决定、角色间关系/好感的变化、已获线索与关键对话要点。不要输出对话原文，不要加评论。"""


class HistoryCompressor:
    def __init__(
        self,
        llm: LLMClient,
        threshold_chars: int = 6000,
        keep_recent: int = 6,
        max_summary_chars: int = 800,
    ):
        self.llm = llm
        self.threshold_chars = threshold_chars
        self.keep_recent = keep_recent
        self.max_summary_chars = max_summary_chars

    def compress(self, history) -> bool:
        """历史超长时压缩早期对话；成功返回 True，无需压缩或失败返回 False。"""
        messages = history.messages
        if len(messages) <= self.keep_recent:
            return False
        total = sum(len(str(m.get("content", ""))) for m in messages)
        if total <= self.threshold_chars:
            return False

        old = messages[:-self.keep_recent]
        keep = messages[-self.keep_recent:]
        prompt_messages = [
            {"role": "system", "content": _SUMMARY_PROMPT},
            *[
                {"role": m["role"], "content": str(m.get("content", ""))}
                for m in old
            ],
            {
                "role": "user",
                "content": "请输出上述历史的剧情回顾摘要。",
            },
        ]
        try:
            summary = self.llm.generate_text(prompt_messages).strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("记忆压缩失败（保持原历史）: %s", exc)
            return False
        if not summary:
            return False
        summary = summary[: self.max_summary_chars]

        history.summary = summary
        history.messages = keep
        return True