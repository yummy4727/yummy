"""Agent 单段工作流：输入审查 → 规则触发 → 沙箱执行 → LLM 生成 → 输出审查。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from paotuan.censor import CompositeCensor, RemoteCensor, SensitiveFilter
from paotuan.context import History, HistoryCompressor, state_summary
from paotuan.llm import LLMClient
from paotuan.loader.package import ScriptPackage
from paotuan.sandbox import SandboxRunner
from paotuan.state import StateManager
from paotuan.workflow.generate import generate_text_with_censor
from paotuan.workflow.intent import route_intent
from paotuan.workflow.rules import parse_rules, triggered_calls
from paotuan.workflow.state_update import execute_calls

logger = logging.getLogger(__name__)


@dataclass
class NarrativeResult:
    text: str
    ok: bool
    state: dict = field(default_factory=dict)
    system_messages: list[str] = field(default_factory=list)
    error: str = ""


class Agent:
    """每轮玩家输入触发一次 handle_player_input。"""

    def __init__(
        self,
        package: ScriptPackage,
        llm: LLMClient,
        state: StateManager,
        runner: SandboxRunner | None = None,
        history: History | None = None,
        censor: SensitiveFilter | None = None,
        remote_censor: RemoteCensor | None = None,
        intent_routing: bool = False,
        compressor: HistoryCompressor | None = None,
    ):
        self.package = package
        self.llm = llm
        self.state = state
        self.runner = runner or SandboxRunner()
        self.history = history or History()
        self.checker = CompositeCensor(censor or SensitiveFilter(), remote_censor)
        self.intent_routing = intent_routing
        self.compressor = compressor
        self._pending_system_messages: list[str] = []

    def handle_player_input(self, text: str) -> NarrativeResult:
        text = text.strip()
        if not text:
            return NarrativeResult(text="", ok=False, error="输入为空")

        if self.checker.check(text):
            return NarrativeResult(
                text="", ok=False, error="输入包含违规内容，请修改后重试。"
            )

        try:
            output = self._run(text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent 处理失败")
            return NarrativeResult(text="", ok=False, error=f"处理失败: {exc}")

        return NarrativeResult(
            text=output,
            ok=True,
            state=self.state.get(),
            system_messages=list(self._pending_system_messages),
        )

    def _run(self, text: str) -> str:
        state = self.state.get()
        if self.intent_routing:
            verdict = route_intent(self.llm, self.package, state, self.history, text)
            calls = verdict.script_calls if verdict.action == "script" else []
        else:
            calls = triggered_calls(parse_rules(self.package.story_script), state)

        new_state, system_messages = execute_calls(self.package, self.runner, state, calls)
        self._pending_system_messages = system_messages
        if new_state is not state:
            self.state.replace(new_state)

        if self.compressor is not None:
            self.compressor.compress(self.history)

        messages = self._build_messages(text)
        output = generate_text_with_censor(self.llm, messages, self.checker)

        self.history.add_user(text)
        self.history.add_assistant(output)
        self.state.clear_system_message()
        return output

    def _build_messages(self, user_text: str) -> list[dict[str, str]]:
        state = self.state.get()
        system_parts = [
            self.package.system_prompt,
            "## 故事脚本指引\n" + self.package.story_script,
            "## 当前状态\n" + state_summary(state),
        ]
        messages: list[dict[str, str]] = [
            {"role": "system", "content": "\n\n".join(system_parts)}
        ]
        for msg in self.history.as_list():
            messages.append(msg)
        messages.append({"role": "user", "content": user_text})
        return messages

    # --------------------------------------------------------- 开场引导
    OPENING_INSTRUCTION = (
        "请为玩家开场。根据《故事脚本指引》与《当前状态》，用叙事者口吻描述："
        "① 玩家当前所处的时间地点与处境；② 正在发生或即将发生的事件；"
        "③ 以「你现在可以：」列出 2~3 个具体可做的行动建议。"
        "直接开始叙述正文，不要输出任务说明或指令。"
    )

    def generate_opening(self) -> NarrativeResult:
        """按当前剧本与状态生成开场引导，并写入历史（不触发规则脚本）。"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "\n\n".join(
                        [
                            self.package.system_prompt,
                            "## 故事脚本指引\n" + self.package.story_script,
                            "## 当前状态\n" + state_summary(self.state.get()),
                        ]
                    ),
                },
                {"role": "user", "content": self.OPENING_INSTRUCTION},
            ]
            output = generate_text_with_censor(self.llm, messages, self.checker)
        except Exception as exc:  # noqa: BLE001
            logger.exception("开场引导生成失败")
            return NarrativeResult(text="", ok=False, error=f"开场失败: {exc}")

        self.history.add_assistant(output)
        return NarrativeResult(
            text=output, ok=True, state=self.state.get(), system_messages=[]
        )
