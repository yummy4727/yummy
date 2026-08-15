"""关键 game_state 字段白名单注入。"""

from __future__ import annotations

import json

# 注入 Prompt 的字段白名单；其余状态仍完整存档但不注入文本。
DEFAULT_INJECT_FIELDS = ("chapter", "weather", "player_name", "affection", "inventory")


def state_summary(
    state: dict,
    fields: tuple[str, ...] = DEFAULT_INJECT_FIELDS,
    max_len: int = 2000,
) -> str:
    subset = {k: state.get(k) for k in fields if k in state}
    if state.get("_system_message"):
        subset["_system_message"] = state["_system_message"]
    text = json.dumps(subset, ensure_ascii=False, indent=2)
    return text[:max_len]
