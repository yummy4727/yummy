"""建立 scripts/ 目录的脚本索引（文件名 = 可调用函数名）。"""

from __future__ import annotations

from pathlib import Path


def build_script_index(scripts_dir: Path) -> dict[str, Path]:
    """返回 {函数名: 脚本路径}。函数名取文件名主干（如 unlock_clue.py -> unlock_clue）。"""
    index: dict[str, Path] = {}
    if not scripts_dir.is_dir():
        return index
    for p in sorted(scripts_dir.glob("*.py")):
        index[p.stem] = p
    return index