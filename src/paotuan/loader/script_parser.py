"""读取 system_prompt.md 与 story_script.md。"""

from __future__ import annotations

from pathlib import Path

from .errors import PackageSecurityError


def parse_scripts(root: Path) -> tuple[str, str]:
    prompt = _read_md(root / "system_prompt.md", "system_prompt.md")
    story = _read_md(root / "story_script.md", "story_script.md")
    return prompt, story


def _read_md(path: Path, name: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PackageSecurityError(f"无法读取 {name}: {exc}") from exc