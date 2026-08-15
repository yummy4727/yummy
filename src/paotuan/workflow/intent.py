"""M2 两段式意图路由：LLM 拆解玩家意图 → 白名单校验 → 修复重试 → 路由。

首段：把「玩家输入 + 当前状态摘要 + 近期对话」交给 LLM，用 JSON 模式输出
`{action, thought, script_calls}`。

次段：对输出做校验与路由——
- `action` 仅允许 `dialogue` / `script`，未知一律按 `dialogue` 兜底；
- `script_calls[].function` 必须在剧本脚本索引（白名单）内，`kwargs` 必须是对象；
- 非法函数逐个丢弃；若 `action=script` 却无一合法调用，则带修正反馈重试（上限 N 次），
  仍失败则降级为 `dialogue`；
- 无论哪条路径，最终都不影响正文文本生成。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from paotuan.context import state_summary
from paotuan.llm import LLMClient
from paotuan.loader.package import ScriptPackage
from paotuan.sandbox import MAX_CALLS_PER_TURN
from paotuan.workflow.rules import ScriptCall

logger = logging.getLogger(__name__)


@dataclass
class IntentVerdict:
    """意图拆解结论：action ∈ {dialogue, script}，dialogue 时 script_calls 恒为空。"""

    action: str
    thought: str = ""
    script_calls: list[ScriptCall] = field(default_factory=list)

#: 允许的 action 取值
VALID_ACTIONS = ("dialogue", "script")

_INTENT_SYSTEM = """你是互动叙事游戏的「意图拆解器」，只负责判断玩家这句话想触发什么，不负责写正文。
输出必须是合法 JSON 对象，格式：
{
  "action": "dialogue" | "script",
  "thought": "用一句话说明你对玩家意图的推断",
  "script_calls": [
    {"function": "脚本函数名", "kwargs": {参数键: 值}}
  ]
}
判断规则：
- 玩家只是在聊天、询问、探索、观察、对话 → action 为 "dialogue"，script_calls 为空数组。
- 玩家明确触发某段剧情机制（解锁线索、改变好感、获得物品、推进章节等），且
  存在对应脚本函数时 → action 为 "script"，并把要调用的函数与参数填入 script_calls。
- 不确定时一律选 "dialogue"。
"""


class IntentError(RuntimeError):
    """意图拆解连续失败（JSON 解析或校验超限）。"""


def route_intent(
    llm: LLMClient,
    package: ScriptPackage,
    state: dict,
    history,
    user_text: str,
    max_retries: int = 2,
    max_calls: int = MAX_CALLS_PER_TURN,
) -> "IntentVerdict":
    """首段：LLM 拆解意图，次段：校验 + 修复重试，返回最终意图结论。"""
    available = sorted(package.script_index)
    messages = _build_prompt_messages(package, state, history, user_text, available)
    last_error = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            messages = messages + [
                {
                    "role": "system",
                    "content": (
                        f"你上一次的输出无效：{last_error}。"
                        f"可用函数：{', '.join(available) or '（无）'}。请重新只输出合法 JSON。"
                    ),
                }
            ]
        try:
            data = llm.generate_json(messages)
        except Exception as exc:  # noqa: BLE001
            last_error = f"JSON 解析失败：{exc}"
            logger.warning("意图拆解 JSON 失败（第 %d 次）: %s", attempt + 1, last_error)
            continue

        verdict = _parse_verdict(data, package, max_calls)
        if verdict.action == "dialogue":
            return verdict
        if verdict.script_calls:
            return verdict
        last_error = (
            "action 为 script 但 script_calls 全部非法或为空"
            "（函数名必须属于可用函数、kwargs 必须是对象）"
        )
        logger.warning("意图校验失败（第 %d 次）: %s", attempt + 1, last_error)

    return IntentVerdict(action="dialogue", thought=f"（意图拆解失败，按对话处理：{last_error}）")


def _build_prompt_messages(
    package: ScriptPackage, state: dict, history, user_text: str, available: list[str]
) -> list[dict[str, str]]:
    turns: list[str] = []
    for msg in history.as_list():
        role = "玩家" if msg.get("role") == "user" else "叙述者"
        turns.append(f"{role}：{msg.get('content', '')}")
    hist_text = "\n".join(turns) if turns else "（暂无对话）"

    funcs = "\n".join(f"- {name}" for name in available) or "- （无可用函数）"
    system = (
        _INTENT_SYSTEM
        + "\n\n本剧本可用脚本函数：\n"
        + funcs
        + "\n（只能调用以上函数；不相关的调用会被丢弃。）"
    )
    user = (
        "## 当前状态\n"
        + state_summary(state)
        + "\n\n## 对话历史\n"
        + hist_text
        + "\n\n## 玩家最新输入\n"
        + user_text
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_verdict(data: object, package: ScriptPackage, max_calls: int) -> "IntentVerdict":
    if not isinstance(data, dict):
        return IntentVerdict(action="dialogue", thought="（输出非 JSON 对象）")
    action = data.get("action")
    if action not in VALID_ACTIONS:
        action = "dialogue"
    thought = str(data.get("thought", ""))[:500]

    calls: list[ScriptCall] = []
    raw_calls = data.get("script_calls") or []
    if isinstance(raw_calls, list):
        for item in raw_calls[:max_calls]:
            if not isinstance(item, dict):
                continue
            fn = item.get("function")
            if not isinstance(fn, str) or package.function_path(fn) is None:
                logger.info("丢弃未知脚本函数: %s", fn)
                continue
            kwargs = item.get("kwargs")
            if kwargs is None:
                kwargs = {}
            if not isinstance(kwargs, dict):
                logger.info("丢弃非法 kwargs（非对象）: %s", fn)
                continue
            calls.append(ScriptCall(function=fn, kwargs=kwargs))

    if action == "script" and not calls:
        # 校验不过：交给调用方决定是否重试
        pass
    return IntentVerdict(action=action, thought=thought, script_calls=calls)