"""玩家输入栏。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class InputBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("描述你的行动或对话…")
        self.send_btn = QPushButton("发送")
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.send_btn)
        self.edit.returnPressed.connect(self.send_btn.click)