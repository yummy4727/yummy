"""叙事文本展示区。"""

from __future__ import annotations

from PySide6.QtWidgets import QTextBrowser


class StoryView(QTextBrowser):
    def append_narrative(self, text: str, role: str = "assistant") -> None:
        if role == "user":
            self.append(f"<p style='color:#1a73e8'><b>玩家：</b></p>")
            self.append(f"<p>{_escape(text)}</p>")
        else:
            self.append(f"<p><b>叙述者：</b></p>")
            self.append(f"<p>{_escape(text)}</p>")

    def append_system(self, text: str) -> None:
        self.append(f"<p style='color:#888'>{_escape(text)}</p>")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )