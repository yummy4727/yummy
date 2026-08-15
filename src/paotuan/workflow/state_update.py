"""状态更新：调用脚本 → 沙箱执行 → 合并状态 → 收集系统消息。"""

from __future__ import annotations

import logging

from paotuan.loader.package import ScriptPackage
from paotuan.sandbox import MAX_CALLS_PER_TURN, SandboxRunner, ScriptResult
from paotuan.workflow.rules import ScriptCall

logger = logging.getLogger(__name__)


def execute_calls(
    package: ScriptPackage,
    runner: SandboxRunner,
    state: dict,
    calls: list[ScriptCall],
) -> tuple[dict, list[str]]:
    """按顺序执行脚本调用，返回 (最终状态, 系统消息列表)。

    函数名对照脚本索引做白名单校验；未命中则跳过并记录系统消息。
    """
    current = state
    messages: list[str] = []
    executed = 0
    for call in calls[:MAX_CALLS_PER_TURN]:
        path = package.function_path(call.function)
        if path is None:
            logger.warning("未索引的脚本函数被调用: %s", call.function)
            messages.append(f"【系统】未知脚本函数: {call.function}")
            continue
        try:
            result: ScriptResult = runner.execute(path, current, call.kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.exception("沙箱执行异常: %s", call.function)
            messages.append(f"【系统】脚本 {call.function} 执行异常: {exc}")
            continue
        if not result.ok:
            logger.warning("脚本失败 %s: %s", call.function, result.error)
            messages.append(f"【系统】脚本 {call.function} 执行失败: {result.error}")
            continue
        executed += 1
        current = result.state
        if isinstance(current, dict) and current.get("_system_message"):
            messages.append(str(current["_system_message"]))
            current = dict(current)
            current.pop("_system_message", None)
    if executed == 0:
        return state, messages
    return current, messages
