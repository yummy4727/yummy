"""共享测试工具：构建剧本 zip。"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

CONFIG = {
    "id": "test-0001",
    "title": "测试剧本",
    "author": "tester",
    "version": "1.0.0",
    "tags": ["测试"],
    "description": "test",
    "rating": "teen",
    "parent_id": None,
    "initial_state": "game_state.json",
}

SYSTEM_PROMPT = (
    "你是测试叙事的叙述者。\n"
    "规则：玩家只能描述自己的行动和语言。\n"
    "禁忌：禁止透露凶手身份。"
)

STORY_SCRIPT = """# 第一章

[脚本: add_affection(target="butler", amount=1)]

**如果** affection.butler >= 3 **则**
  [脚本: unlock_clue(clue="管家的微笑")]
**否则**
  管家只是点头。
**结束**

**如果** weather == "stormy" **则**
  [脚本: unlock_clue(clue="暴雨中的脚印")]
**结束**
"""

GAME_STATE = {
    "chapter": 1,
    "weather": "stormy",
    "affection": {"count": 0, "butler": 0},
    "inventory": ["邀请函"],
    "clues_unlocked": [],
}

ADD_AFFECTION = '''def run(state: dict, **kwargs):
    target = kwargs.get("target")
    amount = kwargs.get("amount", 1)
    aff = state.setdefault("affection", {})
    if target:
        aff[target] = aff.get(target, 0) + amount
    return state
'''

UNLOCK_CLUE = '''def run(state: dict, **kwargs):
    clue = kwargs.get("clue")
    clues = state.setdefault("clues_unlocked", [])
    if clue and clue not in clues:
        clues.append(clue)
        state["_system_message"] = "【系统】获得新线索：" + clue
    return state
'''

SCRIPTS = {
    "add_affection.py": ADD_AFFECTION,
    "unlock_clue.py": UNLOCK_CLUE,
}


def build_package(tmp_path: Path, name: str = "story.zip") -> Path:
    """在 tmp_path 下构造标准剧本 zip，返回 zip 路径。"""
    root = tmp_path / "story_src"
    (root / "scripts").mkdir(parents=True)
    (root / "config.json").write_text(json.dumps(CONFIG, ensure_ascii=False), encoding="utf-8")
    (root / "system_prompt.md").write_text(SYSTEM_PROMPT, encoding="utf-8")
    (root / "story_script.md").write_text(STORY_SCRIPT, encoding="utf-8")
    (root / "game_state.json").write_text(json.dumps(GAME_STATE, ensure_ascii=False), encoding="utf-8")
    for fn, code in SCRIPTS.items():
        (root / "scripts" / fn).write_text(code, encoding="utf-8")

    zip_path = tmp_path / name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(root.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(root))
    return zip_path


def write_zip(tmp_path: Path, entries: dict[str, bytes | str]) -> Path:
    """按 {zip 内路径: 内容} 构造 zip（用于安全用例）。"""
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return zip_path
