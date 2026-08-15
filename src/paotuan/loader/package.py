"""剧本包加载：zip 安全解压、结构校验与包对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from .config_parser import parse_config, validate_metadata
from .errors import PackageSecurityError
from .indexer import build_script_index
from .script_parser import parse_scripts

REQUIRED_FILES = ("config.json", "system_prompt.md", "story_script.md", "game_state.json")

ALLOWED_EXTENSIONS = {
    ".json", ".md", ".py", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
}


@dataclass
class ZipLimits:
    """zip 防护阈值（防 zip bomb / zip slip）。"""

    max_total_uncompressed: int = 100 * 1024 * 1024  # 100MB
    max_entries: int = 1000
    max_ratio: float = 200.0  # 压缩比上限


@dataclass
class ScriptPackage:
    """已加载的剧本项目文件包。"""

    root: Path
    config: dict
    system_prompt: str
    story_script: str
    initial_state: dict
    script_index: dict[str, Path]
    extra_files: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.config.get("title", "未命名剧本")

    def function_path(self, name: str) -> Path | None:
        return self.script_index.get(name)


def _is_safe_entry(name: str) -> bool:
    if not name or name.startswith("/") or "\x00" in name:
        return False
    parts = name.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return False
    if len(parts) >= 1 and ":" in parts[0]:
        return False  # 盘符（C:\ 或 C:）
    return True


def _check_zip(zip_path: Path, limits: ZipLimits) -> None:
    infos: list[ZipInfo] = []
    try:
        with ZipFile(zip_path) as zf:
            infos = zf.infolist()
    except Exception as exc:  # noqa: BLE001
        raise PackageSecurityError(f"zip 无法打开: {exc}") from exc

    if len(infos) > limits.max_entries:
        raise PackageSecurityError(
            f"条目数 {len(infos)} 超过上限 {limits.max_entries}（疑似 zip bomb）"
        )

    total = 0
    for info in infos:
        if not _is_safe_entry(info.filename):
            raise PackageSecurityError(f"非法条目标名: {info.filename!r}（路径穿越）")
        if info.is_dir():
            continue
        if info.file_size > limits.max_total_uncompressed:
            raise PackageSecurityError(f"单个文件过大: {info.filename}")
        if info.compress_size and info.file_size / info.compress_size > limits.max_ratio:
            raise PackageSecurityError(f"压缩比异常: {info.filename}（疑似 zip bomb）")
        total += info.file_size
        if total > limits.max_total_uncompressed:
            raise PackageSecurityError(f"总解压体积超过上限（疑似 zip bomb）")


def _extract_safely(zip_path: Path, dest: Path, limits: ZipLimits) -> None:
    _check_zip(zip_path, limits)
    dest.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not _is_safe_entry(info.filename):
                raise PackageSecurityError(f"非法条目标名: {info.filename!r}")
            target = dest.joinpath(*info.filename.replace("\\", "/").split("/"))
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if target.suffix.lower() not in ALLOWED_EXTENSIONS:
                raise PackageSecurityError(f"不允许的扩展名: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                while chunk := src.read(1024 * 1024):
                    out.write(chunk)


def _validate_structure(root: Path) -> None:
    missing = [f for f in REQUIRED_FILES if not (root / f).is_file()]
    if missing:
        raise PackageSecurityError(f"缺少必需文件: {', '.join(missing)}")


def load_package(zip_path: str | Path, work_dir: Path | None = None) -> ScriptPackage:
    """解压并加载剧本包，返回 ScriptPackage。

    所有解压校验失败均抛出 PackageSecurityError。
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise PackageSecurityError(f"剧本文件不存在: {zip_path}")

    root = work_dir if work_dir is not None else Path(zip_path).with_suffix("") / "extracted"
    _extract_safely(zip_path, root, ZipLimits())
    _validate_structure(root)

    config = parse_config(root / "config.json")
    validate_metadata(config)
    system_prompt, story_script = parse_scripts(root)
    initial_state = _load_initial_state(root, config)
    script_index = build_script_index(root / "scripts")

    extra_files = [
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
    ]
    return ScriptPackage(
        root=root,
        config=config,
        system_prompt=system_prompt,
        story_script=story_script,
        initial_state=initial_state,
        script_index=script_index,
        extra_files=extra_files,
    )


def _load_initial_state(root: Path, config: dict) -> dict:
    initial = config.get("initial_state") or "game_state.json"
    path = root / initial
    if not path.is_file():
        raise PackageSecurityError(f"初始状态文件不存在: {initial}")
    return parse_config(path)
