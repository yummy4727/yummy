"""本地剧本库 / 存档列表（M1 最小实现：提供读档入口）。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget


def pick_script(parent: QWidget | None = None) -> Path | None:
    path, _ = QFileDialog.getOpenFileName(
        parent, "打开剧本项目文件", "", "剧本项目 (*.zip);;所有文件 (*.*)"
    )
    return Path(path) if path else None


def pick_save_file(parent: QWidget | None = None) -> Path | None:
    path, _ = QFileDialog.getSaveFileName(
        parent, "保存存档", "savegame.json", "JSON (*.json)"
    )
    return Path(path) if path else None


def pick_load_file(parent: QWidget | None = None) -> Path | None:
    path, _ = QFileDialog.getOpenFileName(
        parent, "读取存档", "", "JSON (*.json)"
    )
    return Path(path) if path else None