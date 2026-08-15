"""game_state 状态管理器：内存镜像、线程安全读写、存档/读档。"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path


class StateManager:
    """持有 game_state 内存镜像，供 Agent 工作流在后台线程并发访问。

    对外统一返回深拷贝，写入通过 replace/update 显式提交。
    """

    def __init__(self, initial: dict | None = None, autosave_path: Path | None = None):
        self._lock = threading.RLock()
        self._state: dict = copy.deepcopy(initial) if initial is not None else {}
        self._autosave_path = autosave_path

    def get(self) -> dict:
        """返回当前状态深拷贝。"""
        with self._lock:
            return copy.deepcopy(self._state)

    def replace(self, new_state: dict) -> dict:
        """整体替换状态（沙箱脚本返回的合并结果）。"""
        if not isinstance(new_state, dict):
            raise TypeError("状态必须是 dict")
        with self._lock:
            self._state = copy.deepcopy(new_state)
            self._autosave()
            return copy.deepcopy(self._state)

    def update(self, delta: dict) -> dict:
        """浅合并小改动（如设置 _system_message）。"""
        if not isinstance(delta, dict):
            raise TypeError("delta 必须是 dict")
        with self._lock:
            self._state.update(copy.deepcopy(delta))
            self._autosave()
            return copy.deepcopy(self._state)

    def clear_system_message(self) -> None:
        """每轮结束后清空 _system_message，防止泄漏进下一轮 Prompt。"""
        with self._lock:
            self._state.pop("_system_message", None)
            self._autosave()

    def save(self, path: Path | None = None) -> Path:
        with self._lock:
            target = path or self._autosave_path
            if target is None:
                raise ValueError("未指定存档路径")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return target

    def load(self, path: Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("存档必须是 JSON 对象")
        with self._lock:
            self._state = data
            self._autosave()

    def _autosave(self) -> None:
        if self._autosave_path is not None:
            try:
                self._autosave_path.parent.mkdir(parents=True, exist_ok=True)
                self._autosave_path.write_text(
                    json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except OSError:
                pass