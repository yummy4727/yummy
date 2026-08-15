"""state：读写与存档。"""

from __future__ import annotations

from paotuan.state import StateManager, save_state, load_state
from paotuan.state.persistence import autosave_dir


def test_autosave_dir_is_stable_per_file(tmp_path):
    script = tmp_path / "story.zip"
    script.write_bytes(b"same-content")
    d1 = autosave_dir(tmp_path / "data", script)
    d2 = autosave_dir(tmp_path / "data", script)
    assert d1 == d2


def test_autosave_dir_changes_with_content(tmp_path):
    script = tmp_path / "story.zip"
    script.write_bytes(b"v1")
    d1 = autosave_dir(tmp_path / "data", script)
    script.write_bytes(b"v2")
    d2 = autosave_dir(tmp_path / "data", script)
    assert d1 != d2


def test_get_returns_copy():
    sm = StateManager({"a": 1})
    got = sm.get()
    got["a"] = 999
    assert sm.get()["a"] == 1  # 隔离，防止外部改原始数据


def test_replace():
    sm = StateManager({"a": 1})
    sm.replace({"a": 2, "b": 3})
    assert sm.get() == {"a": 2, "b": 3}


def test_update_shallow_merge():
    sm = StateManager({"affection": {"butler": 0, "count": 1}})
    sm.update({"weather": "stormy"})
    assert sm.get()["weather"] == "stormy"
    assert sm.get()["affection"]["butler"] == 0


def test_update_rejects_non_dict():
    sm = StateManager({"a": 1})
    try:
        sm.update("not-a-dict")
        assert False, "应抛 TypeError"
    except TypeError:
        pass


def test_clear_system_message():
    sm = StateManager({"a": 1, "_system_message": "x"})
    sm.clear_system_message()
    assert "_system_message" not in sm.get()


def test_autosave_on_mutation(tmp_path):
    path = tmp_path / "s" / "state.json"
    sm = StateManager({"a": 1}, autosave_path=path)
    sm.replace({"a": 2})
    assert load_state(path) == {"a": 2}
    sm.update({"b": 3})
    assert load_state(path) == {"a": 2, "b": 3}


def test_autosave_clears_system_message(tmp_path):
    path = tmp_path / "s" / "state.json"
    sm = StateManager({"a": 1}, autosave_path=path)
    sm.update({"_system_message": "secret"})
    sm.clear_system_message()
    assert "_system_message" not in load_state(path)


def test_save_load_roundtrip(tmp_path):
    sm = StateManager({"a": 1, "nested": {"b": [1, 2]}})
    path = tmp_path / "save.json"
    sm.save(path)
    loaded = load_state(path)
    assert loaded == {"a": 1, "nested": {"b": [1, 2]}}

    sm2 = StateManager({})
    sm2.load(path)
    assert sm2.get() == {"a": 1, "nested": {"b": [1, 2]}}