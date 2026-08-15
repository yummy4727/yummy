"""存档/读档的序列化封装。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def autosave_dir(data_dir: Path, script_path: Path) -> Path:
    """按剧本文件内容哈希分配专属自动存档目录，剧本内容一变即重新开始。"""
    digest = hashlib.sha256(Path(script_path).read_bytes()).hexdigest()[:16]
    return Path(data_dir) / "saves" / digest


def save_state(state: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_state(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("存档必须是 JSON 对象")
    return data
