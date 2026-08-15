"""workflow：单段闭环集成测试（注入假 LLM，不联网）。"""

from __future__ import annotations

from conftest import build_package

from paotuan.context import History
from paotuan.loader import load_package
from paotuan.state import StateManager
from paotuan.state.persistence import autosave_dir
from paotuan.workflow import Agent


class FakeLLM:
    def __init__(self, responses=None, default="（假 LLM 叙述文本。）"):
        self.responses = list(responses or [])
        self.default = default
        self.calls = []

    def generate_text(self, messages):
        self.calls.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return self.default


class SensitiveInput:
    def check(self, text):
        return "炸弹" in text


def _make_agent(tmp_path, llm=None):
    zip_path = build_package(tmp_path)
    pkg = load_package(zip_path, work_dir=tmp_path / "out")
    state = StateManager(pkg.initial_state)
    agent = Agent(package=pkg, llm=llm or FakeLLM(), state=state)
    return agent, pkg, state


def test_agent_end_to_end(tmp_path):
    agent, pkg, state = _make_agent(tmp_path)
    result = agent.handle_player_input("我走进庄园大门。")

    assert result.ok
    assert "假 LLM" in result.text

    # 无条件 add_affection 应执行
    assert state.get()["affection"]["butler"] == 1

    # weather == stormy → unlock_clue 应执行
    assert "暴雨中的脚印" in state.get()["clues_unlocked"]

    # _system_message 被提取进 system_messages 且不残留 state
    assert any("脚印" in m for m in result.system_messages)
    assert "_system_message" not in state.get()


def test_agent_history_grows(tmp_path):
    agent, _, _ = _make_agent(tmp_path)
    agent.handle_player_input("第一句。")
    agent.handle_player_input("第二句。")
    history = agent.history.as_list()
    assert [h["role"] for h in history] == ["user", "assistant", "user", "assistant"]


def test_agent_censors_input(tmp_path):
    agent, pkg, state = _make_agent(tmp_path)
    result = agent.handle_player_input("我想制造炸弹。")
    assert not result.ok
    assert "违规" in result.error
    # 状态未被修改
    assert state.get()["affection"]["butler"] == 0


def test_agent_prompt_contains_system_parts(tmp_path):
    fake = FakeLLM()
    agent, pkg, _ = _make_agent(tmp_path, llm=fake)
    agent.handle_player_input("你好。")
    system_content = fake.calls[0][0]["content"]
    assert pkg.system_prompt in system_content
    assert "故事脚本" in system_content
    assert "当前状态" in system_content
    # 最后一轮消息为用户输入
    assert fake.calls[0][-1] == {"role": "user", "content": "你好。"}


def test_agent_censors_output_with_fallback(tmp_path):
    class AlwaysBadLLM:
        def generate_text(self, messages):
            return "我们决定安放炸弹。"

    agent, _, state = _make_agent(tmp_path, llm=AlwaysBadLLM())
    result = agent.handle_player_input("继续。")
    assert result.ok
    assert result.text == "（生成内容未通过安全审查，已替换为兜底回复。）"


def test_generate_opening_returns_text_and_fills_history(tmp_path):
    fake = FakeLLM(default="（开场引导文本）你现在可以：查看尸体、询问仆人、离开房间。")
    agent, pkg, state = _make_agent(tmp_path, llm=fake)

    result = agent.generate_opening()

    assert result.ok
    assert "开场引导" in result.text
    # 开场写入历史（assistant 角色），且不执行规则脚本（无脚本副作用）
    assert [h["role"] for h in agent.history.as_list()] == ["assistant"]
    assert state.get()["affection"]["butler"] == 0
    # 提示词包含开场指令
    assert Agent.OPENING_INSTRUCTION in fake.calls[0][-1]["content"]
    assert pkg.system_prompt in fake.calls[0][0]["content"]


def test_generate_opening_failure_returns_error(tmp_path):
    class BoomLLM:
        def generate_text(self, messages):
            raise RuntimeError("网络错误")

    agent, _, _ = _make_agent(tmp_path, llm=BoomLLM())
    result = agent.generate_opening()
    assert not result.ok
    assert "开场失败" in result.error


def test_session_resumes_after_restart(tmp_path):
    """模拟重启：状态+历史自动落盘，重开同剧本后从上次进度继续。"""
    zip_path = build_package(tmp_path)
    pkg = load_package(zip_path, work_dir=tmp_path / "out")
    save_dir = autosave_dir(tmp_path / "data", zip_path)

    # 首次游玩（等价于 load_script：StateManager 绑定 autosave 路径）
    state = StateManager(pkg.initial_state, autosave_path=save_dir / "state.json")
    agent = Agent(package=pkg, llm=FakeLLM(), state=state, history=History())
    agent.handle_player_input("我敲了敲大门。")
    assert state.get()["affection"]["butler"] == 1
    agent.history.save(save_dir / "history.json")  # 等价于 _on_result 里的 _save_history

    # 退出后重开：仍用同一 autosave 路径 → 恢复上次状态
    state2 = StateManager(pkg.initial_state, autosave_path=save_dir / "state.json")
    state2.load(save_dir / "state.json")
    assert state2.get()["affection"]["butler"] == 1
    assert "暴雨中的脚印" in state2.get()["clues_unlocked"]

    hist2 = History()
    hist2.load(save_dir / "history.json")
    assert [h["role"] for h in hist2.as_list()] == ["user", "assistant"]

    # 基于恢复后的状态继续游玩
    agent2 = Agent(
        package=pkg,
        llm=FakeLLM(),
        state=state2,
        history=hist2,
    )
    result = agent2.handle_player_input("我推开门。")
    assert result.ok
    assert agent2.history.as_list()[-1] == {"role": "assistant", "content": result.text}