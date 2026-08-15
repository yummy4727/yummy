"""状态/线索/背包面板。"""

from __future__ import annotations

import json

from PySide6.QtWidgets import QPlainTextEdit


class StatePanel(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("游戏状态将在运行时显示")

    def refresh(self, state: dict) -> None:
        text = json.dumps(state, ensure_ascii=False, indent=2)
        self.setPlainText(text)