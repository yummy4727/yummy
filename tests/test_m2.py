"""M2：两段式意图路由（intent）、远程审查（censor）、记忆压缩（context）、衍生导出（generator）。"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import httpx

from conftest import build_package

from paotuan.censor import CompositeCensor, RemoteCensor, SensitiveFilter
from paotuan.context import History, HistoryCompressor
from paotuan.generator import PlaythroughExporter
from paotuan.loader import load_package
from paotuan.state import StateManager
from paotuan.workflow import Agent, route_intent
from paotuan.workflow.rules import ScriptCall

# ---------------------------------------------------------------- 假 LLM


class FakeLLM:
    def __init__(self, json_responses=None, text_responses=None, default_text="（假 LLM 叙述文本。）"):
        self.json_responses = list(json_responses or [])
        self.text_responses = list(text_responses or [])
        self.default_text = default_text
        self.json_calls = []
        self.text_calls = []

    def generate_json(self, messages):
        self.json_calls.append(list(messages))
        if self.json_responses:
            data = self.json_responses.pop(0)
            if isinstance(data, Exception):
                raise data
            return data
        raise AssertionError("未配置 JSON 响应")

    def generate_text(self, messages):
        self.text_calls.append(list(messages))
        if self.text_responses:
            return self.text_responses.pop(0)
        return self.default_text


def _make_agent(tmp_path, llm=None, **kwargs):
    zip_path = build_package(tmp_path)
    pkg = load_package(zip_path, work_dir=tmp_path / "out")
    state = StateManager(pkg.initial_state)
    agent = Agent(package=pkg, llm=llm or FakeLLM(), state=state, **kwargs)
    return agent, pkg, state


# ---------------------------------------------------------------- 意图路由


def test_route_intent_dialogue():
    llm = FakeLLM(json_responses=[{"action": "dialogue", "thought": "闲聊", "script_calls": []}])
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        zip_path = build_package(Path(td))
        pkg = load_package(zip_path, work_dir=Path(td) / "out")
        verdict = route_intent(llm, pkg, pkg.initial_state, History(), "你好。")
        assert verdict.action == "dialogue"
        assert verdict.script_calls == []
        assert "可用脚本函数" in llm.json_calls[0][0]["content"]


def test_route_intent_script_valid():
    llm = FakeLLM(json_responses=[
        {
            "action": "script",
            "thought": "解锁线索",
            "script_calls": [{"function": "unlock_clue", "kwargs": {"clue": "伯爵的警告"}}],
        }
    ])
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        zip_path = build_package(Path(td))
        pkg = load_package(zip_path, work_dir=Path(td) / "out")
        verdict = route_intent(llm, pkg, pkg.initial_state, History(), "我说出了关键秘密。")
        assert verdict.action == "script"
        assert verdict.script_calls == [ScriptCall(function="unlock_clue", kwargs={"clue": "伯爵的警告"})]


def test_route_intent_unknown_function_dropped_then_fallback():
    """非法函数全部被丢弃 → 带修正反馈重试 → 仍失败则兜底 dialogue。"""
    llm = FakeLLM(json_responses=[
        {"action": "script", "thought": "x", "script_calls": [{"function": "not_exist", "kwargs": {}}]},
        {"action": "script", "thought": "x", "script_calls": [{"function": "also_bad", "kwargs": {}}]},
        {"action": "script", "thought": "x", "script_calls": [{"function": "also_bad", "kwargs": {}}]},
    ])
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        zip_path = build_package(Path(td))
        pkg = load_package(zip_path, work_dir=Path(td) / "out")
        verdict = route_intent(llm, pkg, pkg.initial_state, History(), "触发点什么。")
        assert verdict.action == "dialogue"
        assert len(llm.json_calls) == 3  # 初试 + 2 次重试


def test_route_intent_mixed_valid_drops_invalid():
    llm = FakeLLM(json_responses=[
        {
            "action": "script",
            "script_calls": [
                {"function": "unlock_clue", "kwargs": {"clue": "a"}},
                {"function": "hacker", "kwargs": {}},
                {"function": "add_affection", "kwargs": "not-a-dict"},
            ],
        }
    ])
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        zip_path = build_package(Path(td))
        pkg = load_package(zip_path, work_dir=Path(td) / "out")
        verdict = route_intent(llm, pkg, pkg.initial_state, History(), "触发。")
        assert verdict.action == "script"
        assert verdict.script_calls == [ScriptCall(function="unlock_clue", kwargs={"clue": "a"})]


def test_agent_intent_routing_runs_scripts(tmp_path):
    """开启意图路由后，script 意图会真正在沙箱执行并更新状态。"""
    llm = FakeLLM(json_responses=[
        {"action": "script", "thought": "好感达标", "script_calls": [
            {"function": "add_affection", "kwargs": {"target": "butler", "amount": 3}}]},
    ])
    agent, _, state = _make_agent(tmp_path, llm=llm, intent_routing=True)
    result = agent.handle_player_input("我对管家示好。")
    assert result.ok
    assert state.get()["affection"]["butler"] == 3


def test_agent_intent_routing_dialogue_skips_scripts(tmp_path):
    llm = FakeLLM(json_responses=[{"action": "dialogue", "thought": "只是聊天", "script_calls": []}])
    agent, _, state = _make_agent(tmp_path, llm=llm, intent_routing=True)
    result = agent.handle_player_input("随便聊聊。")
    assert result.ok
    assert state.get()["affection"]["butler"] == 0  # 未触发脚本


# ---------------------------------------------------------------- 远程审查


def _fake_moderation(flagged: bool, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"results": [{"flagged": flagged}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_remote_censor_flagged():
    c = RemoteCensor(api_key="sk-x", http=_fake_moderation(True))
    assert c.check("一些违规内容")


def test_remote_censor_clean():
    c = RemoteCensor(api_key="sk-x", http=_fake_moderation(False))
    assert not c.check("普通内容")


def test_remote_censor_disabled_or_no_key():
    assert not RemoteCensor(api_key="").check("违规")
    assert not RemoteCensor(api_key="sk-x", enabled=False).check("违规")


def test_remote_censor_fails_open_on_error():
    def boom(request):
        return httpx.Response(500, text="server error")

    c = RemoteCensor(api_key="sk-x", http=httpx.Client(transport=httpx.MockTransport(boom)))
    assert not c.check("内容")  # 服务异常放行，不阻塞


def test_remote_censor_network_error_fails_open():
    def boom(request):
        raise httpx.ConnectError("offline")

    c = RemoteCensor(api_key="sk-x", http=httpx.Client(transport=httpx.MockTransport(boom)))
    assert not c.check("内容")


def test_composite_censor_local_first():
    composite = CompositeCensor(SensitiveFilter(), RemoteCensor(api_key="sk-x"))
    assert composite.check("我想制作炸弹")  # 本地词库命中，无需远程


def test_composite_censor_remote_hit():
    remote = RemoteCensor(api_key="sk-x", http=_fake_moderation(True))
    composite = CompositeCensor(SensitiveFilter(), remote)
    assert composite.check("这是远程命中的内容")


# ---------------------------------------------------------------- 记忆压缩


def test_history_compressor_summarizes_when_long(tmp_path):
    llm = FakeLLM(text_responses=["（摘要）玩家调查了书房，获得脚印线索。"])
    hist = History()
    for i in range(10):
        hist.add_user(f"玩家第{i}句话：内容比较长，用来撑大历史体积。" * 5)
        hist.add_assistant(f"叙述者第{i}句话：同样填充一些长度。" * 5)
    c = HistoryCompressor(llm, threshold_chars=500, keep_recent=4)
    assert c.compress(hist) is True
    assert len(hist.messages) == 4
    assert hist.summary
    first = hist.as_list()[0]
    assert first["role"] == "system" and "摘要" in first["content"]


def test_history_compressor_skips_when_short():
    hist = History()
    hist.add_user("短")
    hist.add_assistant("短")
    c = HistoryCompressor(FakeLLM(), threshold_chars=1000, keep_recent=4)
    assert c.compress(hist) is False
    assert not hist.summary


def test_history_compressor_failure_keeps_history():
    class BoomLLM:
        def generate_text(self, messages):
            raise RuntimeError("网络错误")

    hist = History()
    for i in range(8):
        hist.add_user("长内容。" * 100)
        hist.add_assistant("长内容。" * 100)
    original = len(hist.messages)
    c = HistoryCompressor(BoomLLM(), threshold_chars=10, keep_recent=4)
    assert c.compress(hist) is False
    assert len(hist.messages) == original


def test_history_summary_persists_roundtrip(tmp_path):
    hist = History()
    hist.add_user("u1")
    hist.add_assistant("a1")
    hist.summary = "早期摘要"
    path = tmp_path / "h.json"
    hist.save(path)
    loaded = History()
    loaded.load(path)
    assert loaded.summary == "早期摘要"
    assert loaded.messages == hist.messages


def test_history_legacy_list_format_load(tmp_path):
    path = tmp_path / "h.json"
    path.write_text(json.dumps([{"role": "user", "content": "旧格式"}]), encoding="utf-8")
    hist = History()
    hist.load(path)
    assert hist.messages == [{"role": "user", "content": "旧格式"}]
    assert hist.summary == ""


def test_agent_compression_integrated(tmp_path):
    llm = FakeLLM(json_responses=[{"action": "dialogue", "thought": "", "script_calls": []}],
                  text_responses=["长叙述。" * 50])
    agent, _, _ = _make_agent(
        tmp_path, llm=llm, intent_routing=True,
        compressor=HistoryCompressor(llm, threshold_chars=100, keep_recent=4),
    )
    for i in range(6):
        agent.handle_player_input("继续。" * 30)
    assert agent.history.summary  # 长历史已被压缩出摘要


# ---------------------------------------------------------------- 衍生导出


def test_exporter_builds_derived_package(tmp_path):
    zip_path = build_package(tmp_path)
    play_state = {"chapter": 3, "affection": {"butler": 5, "count": 1}, "clues_unlocked": ["暴雨中的脚印"]}
    out = PlaythroughExporter().export(
        zip_path, play_state, history_summary="玩家查明了暴雨中的脚印。", player_name="小明",
        output_dir=tmp_path / "outzips",
    )
    assert out.exists()
    assert "小明" in out.name and "旅程" in out.name

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        for required in ("config.json", "system_prompt.md", "story_script.md", "game_state.json"):
            assert required in names
        assert any(n.startswith("scripts/") for n in names)  # 脚本一并复制

        config = json.loads(zf.read("config.json"))
        assert config["parent_id"] == "test-0001"
        assert "小明" in config["title"]

        gs = json.loads(zf.read("game_state.json"))
        assert gs["clues_unlocked"] == ["暴雨中的脚印"]
        assert gs["affection"]["butler"] == 5

        sp = zf.read("system_prompt.md").decode("utf-8")
        assert "测试叙事的叙述者" in sp

        ss = zf.read("story_script.md").decode("utf-8")
        assert "小明" in ss and "暴雨中的脚印" in ss


def test_exporter_requires_dict_state(tmp_path):
    zip_path = build_package(tmp_path)
    try:
        PlaythroughExporter().export(zip_path, "not-a-dict")
        assert False, "应抛 TypeError"
    except TypeError:
        pass


def test_exporter_output_is_loadable_again(tmp_path):
    zip_path = build_package(tmp_path)
    out = PlaythroughExporter().export(
        zip_path, {"chapter": 2}, history_summary="", player_name="小红",
        output_dir=tmp_path / "outzips",
    )
    # 导出物应能作为合法剧本重新加载
    pkg = load_package(out, work_dir=tmp_path / "reload")
    assert pkg.title.endswith("的旅程")
    assert pkg.config.get("parent_id") == "test-0001"