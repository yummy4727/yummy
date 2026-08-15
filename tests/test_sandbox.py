"""sandbox：隔离、超时、白名单。"""

from __future__ import annotations

from conftest import build_package

from paotuan.loader import load_package
from paotuan.sandbox import SandboxRunner, run_script


def _load_pkg(tmp_path):
    zip_path = build_package(tmp_path)
    return load_package(zip_path, work_dir=tmp_path / "out")


def _write_script(tmp_path, name, code):
    p = tmp_path / name
    p.write_text(code, encoding="utf-8")
    return p


def test_run_normal_script(tmp_path):
    script = _write_script(
        tmp_path,
        "ok.py",
        "def run(state, **kwargs):\n"
        "    clues = state.setdefault('clues_unlocked', [])\n"
        "    clues.append(kwargs.get('clue', '?'))\n"
        "    return state\n",
    )
    result = run_script(
        str(script), {"clues_unlocked": []}, {"clue": "钥匙"}, timeout=5.0
    )
    assert result.ok
    assert result.state["clues_unlocked"] == ["钥匙"]


def test_system_message_passthrough(tmp_path):
    script = _write_script(
        tmp_path,
        "sys.py",
        "def run(state, **kwargs):\n"
        "    state['_system_message'] = '【系统】新线索'\n"
        "    return state\n",
    )
    result = run_script(str(script), {}, {}, timeout=5.0)
    assert result.ok
    assert result.state["_system_message"] == "【系统】新线索"


def test_import_os_is_blocked(tmp_path):
    script = _write_script(
        tmp_path,
        "evil.py",
        "import os\n"
        "def run(state, **kwargs):\n"
        "    os.remove('C:/Windows/win.ini')\n"
        "    return state\n",
    )
    result = run_script(str(script), {}, {}, timeout=5.0)
    assert not result.ok
    assert result.error_type == "sandbox"


def test_infinite_loop_times_out(tmp_path):
    script = _write_script(
        tmp_path,
        "loop.py",
        "def run(state, **kwargs):\n"
        "    while True:\n"
        "        pass\n"
        "    return state\n",
    )
    result = run_script(str(script), {}, {}, timeout=1.0)
    assert not result.ok
    assert result.error_type == "timeout"


def test_non_dict_return_rejected(tmp_path):
    script = _write_script(
        tmp_path,
        "bad.py",
        "def run(state, **kwargs):\n"
        "    return 42\n",
    )
    result = run_script(str(script), {}, {}, timeout=5.0)
    assert not result.ok
    assert result.error_type == "sandbox"


def test_kwargs_passed_through(tmp_path):
    script = _write_script(
        tmp_path,
        "kw.py",
        "def run(state, **kwargs):\n"
        "    state['echo'] = kwargs.get('echo')\n"
        "    return state\n",
    )
    result = run_script(str(script), {}, {"echo": "hi"}, timeout=5.0)
    assert result.ok
    assert result.state["echo"] == "hi"


def test_runner_executes_script_from_package(tmp_path):
    pkg = _load_pkg(tmp_path)
    runner = SandboxRunner()
    path = pkg.function_path("add_affection")
    result = runner.execute(path, {"affection": {"butler": 0}}, {"target": "butler", "amount": 2})
    assert result.ok
    assert result.state["affection"]["butler"] == 2
    assert result.elapsed < 5.0