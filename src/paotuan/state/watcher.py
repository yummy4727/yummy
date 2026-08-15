"""状态变更跟踪：记录每次 replace/update 产生的变化（供调试与游玩记录生成）。"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StateChange:
    field: str
    old: Any = None
    new: Any = None


@dataclass
class StateWatcher:
    history: list[dict] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, before: dict, after: dict) -> None:
        before = copy.deepcopy(before)
        after = copy.deepcopy(after)
        with self._lock:
            keys = set(before) | set(after)
            changes = [
                StateChange(k, before.get(k), after.get(k))
                for k in keys
                if before.get(k) != after.get(k)
            ]
            if changes:
                self.history.append(
                    {
                        "changes": [
                            {"field": c.field, "old": c.old, "new": c.new}
                            for c in changes
                        ]
                    }
                )

    def summary(self) -> str:
        with self._lock:
            lines = []
            for i, entry in enumerate(self.history, 1):
                desc = ", ".join(
                    f"{c['field']}: {c['old']!r} -> {c['new']!r}" for c in entry["changes"]
                )
                lines.append(f"[{i}] {desc}")
            return "\n".join(lines) or "（无状态变化）"
