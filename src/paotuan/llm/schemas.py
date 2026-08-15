"""LLM 结构化输出定义。M2 意图拆解使用；M1 仅文本生成。"""

from __future__ import annotations

from typing import Literal, TypedDict


class ScriptCallSpec(TypedDict):
    function: str
    kwargs: dict


class IntentResult(TypedDict):
    action: Literal["dialogue", "script"]
    thought: str
    script_calls: list[ScriptCallSpec]
