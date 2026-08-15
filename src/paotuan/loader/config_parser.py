"""解析 config.json（以及作为初始状态模板的 game_state.json）。"""

from __future__ import annotations

import json
from pathlib import Path

from .errors import PackageSecurityError

_REQUIRED_CONFIG = ("id", "title", "author", "version")


def parse_config(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageSecurityError(f"JSON 解析失败 {path.name}: {exc}") from exc
    except OSError as exc:
        raise PackageSecurityError(f"无法读取 {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise PackageSecurityError(f"{path.name} 顶层必须是 JSON 对象")
    return data


def validate_metadata(config: dict) -> None:
    missing = [k for k in _REQUIRED_CONFIG if k not in config]
    if missing:
        raise PackageSecurityError(f"config.json 缺少字段: {', '.join(missing)}")
    for key in ("title", "author", "id", "version"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise PackageSecurityError(f"config.json 字段 {key} 必须为非空字符串")