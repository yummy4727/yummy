"""对话历史（短期记忆）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class History:
    messages: list[dict[str, str]] = field(default_factory=list)
    max_turns: int = 40
    #: 记忆压缩产物：被摘要替代的早期对话
    summary: str = ""

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})

    def as_list(self) -> list[dict[str, str]]:
        """返回用于 LLM 的 messages（不含系统消息，摘要作为首条 system 注入）。"""
        trimmed = self.messages[-self.max_turns * 2 :]
        out = [dict(m) for m in trimmed]
        if self.summary:
            out.insert(0, {"role": "system", "content": "【历史摘要】" + self.summary})
        return out

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": self.summary, "messages": self.messages}
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load(self, path: Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, list):
            # 兼容旧格式：直接是消息数组
            if self._valid_messages(data):
                self.messages = data
            return
        if not isinstance(data, dict):
            return
        msgs = data.get("messages")
        if isinstance(msgs, list) and self._valid_messages(msgs):
            self.messages = msgs
        self.summary = str(data.get("summary", "")) if data.get("summary") else ""

    @staticmethod
    def _valid_messages(messages: list) -> bool:
        return all(
            isinstance(m, dict) and m.get("role") in ("user", "assistant")
            for m in messages
        )
