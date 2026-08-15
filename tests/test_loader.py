"""loader：zip 安全与结构校验。"""

from __future__ import annotations

import json
import zipfile

import pytest

from conftest import build_package, write_zip

from paotuan.loader import (
    ALLOWED_EXTENSIONS,
    PackageSecurityError,
    load_package,
)


def test_valid_package_loads(tmp_path):
    zip_path = build_package(tmp_path)
    pkg = load_package(zip_path, work_dir=tmp_path / "out")

    assert pkg.title == "测试剧本"
    assert pkg.config["version"] == "1.0.0"
    assert pkg.system_prompt
    assert pkg.story_script
    assert pkg.initial_state["chapter"] == 1
    assert set(pkg.script_index) == {"add_affection", "unlock_clue"}
    assert "脚本" in pkg.story_script


def test_missing_required_file_rejected(tmp_path):
    zip_path = write_zip(tmp_path, {"config.json": json.dumps({"id": "x"})})
    with pytest.raises(PackageSecurityError, match="缺少必需文件"):
        load_package(zip_path, work_dir=tmp_path / "out")


def test_zip_slip_rejected(tmp_path):
    content = json.dumps({"id": "x", "title": "t", "author": "a", "version": "1"})
    zip_path = write_zip(tmp_path, {"../evil.py": "print('boom')"})
    with pytest.raises(PackageSecurityError, match="路径穿越"):
        load_package(zip_path, work_dir=tmp_path / "out")
    # 校验直接走 _extract_safely 也拒绝
    zip_path2 = write_zip(tmp_path, {"config.json": content, "..\\evil.py": "x"})
    with pytest.raises(PackageSecurityError, match="非法条目标名"):
        load_package(zip_path2, work_dir=tmp_path / "out2")


def test_disallowed_extension_rejected(tmp_path):
    entries = {
        "config.json": json.dumps({"id": "x", "title": "t", "author": "a", "version": "1"}),
        "evil.exe": b"MZ",
    }
    zip_path = write_zip(tmp_path, entries)
    with pytest.raises(PackageSecurityError, match="不允许的扩展名"):
        load_package(zip_path, work_dir=tmp_path / "out")


def test_too_many_entries_rejected(tmp_path):
    entries = {f"f{i}.txt": "x" for i in range(1001)}
    zip_path = write_zip(tmp_path, entries)
    with pytest.raises(PackageSecurityError, match="条目数"):
        load_package(zip_path, work_dir=tmp_path / "out")


def test_zip_bomb_ratio_rejected(tmp_path):
    # 10MB 零字节压缩比约 >1000，超过默认上限 200
    zip_path = write_zip(tmp_path, {"config.json": "x" * 10 * 1024 * 1024})
    with pytest.raises(PackageSecurityError, match="压缩比"):
        load_package(zip_path, work_dir=tmp_path / "out")


def test_custom_initial_state_used(tmp_path):
    build_package(tmp_path)
    src = tmp_path / "story_src"
    cfg = json.loads((src / "config.json").read_text(encoding="utf-8"))
    cfg["initial_state"] = "custom_state.json"
    (src / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    (src / "custom_state.json").write_text(
        json.dumps({"custom": True}, ensure_ascii=False), encoding="utf-8"
    )
    zip_path = tmp_path / "story2.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(src.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(src))
    pkg = load_package(zip_path, work_dir=tmp_path / "out3")
    assert pkg.initial_state == {"custom": True}


def test_allowed_extensions_contains_py_md_json():
    assert {".py", ".md", ".json"} <= ALLOWED_EXTENSIONS