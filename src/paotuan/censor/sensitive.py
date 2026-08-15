"""本地敏感词过滤（输入/输出快速拦截）。

默认内置少量「教唆伤害/违法制造」类短语，避免误伤叙事常用词（如"谋杀""枪支"的
正常剧情描述）。任何过滤都只是第一道闸，M2 再接入远程审查。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 默认敏感词：只收录容易触发安全问题的短语
DEFAULT_SENSITIVE_WORDS = frozenset(
    {
        "炸弹",
        "自制爆炸物",
        "制作炸弹",
        "如何制造炸弹",
        "杀人教程",
        "自杀方法",
        "购买枪支",
        "走私毒品",
    }
)


@dataclass
class SensitiveFilter:
    words: set[str] = field(default_factory=lambda: set(DEFAULT_SENSITIVE_WORDS))

    def check(self, text: str) -> bool:
        """返回 True 表示违规。"""
        lowered = text.lower()
        return any(w.lower() in lowered for w in self.words)