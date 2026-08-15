"""游玩记录生成器（M2）：把一次游玩打包成「衍生剧本项目文件」雏形。

产出 `《原剧本名》- 玩家名的旅程.zip`：
- `config.json`：`title` 自动命名，`parent_id` = 原剧本 id；
- `game_state.json`：最终游戏状态；
- `story_script.md`：空模板 + 状态变化摘要（供创作者编辑）；
- `system_prompt.md`：复制原剧本；
- `scripts/`：复制原剧本脚本，保证衍生剧本可继续游玩。
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from paotuan.loader import load_package

_REQUIRED_ENTRIES = ("config.json", "system_prompt.md", "story_script.md", "game_state.json")


class PlaythroughExporter:
    def __init__(self, work_dir: Path | None = None):
        self._work_dir = work_dir

    def export(
        self,
        package_path: Path,
        play_state: dict,
        history_summary: str = "",
        player_name: str = "玩家",
        output_dir: Path | None = None,
    ) -> Path:
        """读取原剧本包并打包衍生剧本 zip，返回 zip 路径。"""
        if not isinstance(play_state, dict):
            raise TypeError("play_state 必须是 dict")
        package_path = Path(package_path)
        package = load_package(package_path, work_dir=self._work_dir)

        out_dir = Path(output_dir) if output_dir else package_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        zip_path = out_dir / self._derive_name(package.title, player_name)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            config = self._derive_config(package, player_name)
            zf.writestr("config.json", json.dumps(config, ensure_ascii=False, indent=2))
            zf.writestr("system_prompt.md", package.system_prompt)
            zf.writestr(
                "story_script.md",
                self._build_story_script(package, play_state, history_summary, player_name),
            )
            zf.writestr(
                "game_state.json",
                json.dumps(play_state, ensure_ascii=False, indent=2),
            )
            self._copy_scripts(zf, package)
        return zip_path

    # ------------------------------------------------------------- 组装
    @staticmethod
    def _derive_config(package, player_name: str) -> dict:
        config = dict(package.config)
        config["title"] = f"《{package.title}》- {player_name}的旅程"
        config["parent_id"] = package.config.get("id")
        config["initial_state"] = "game_state.json"
        return config

    @staticmethod
    def _derive_name(title: str, player_name: str) -> str:
        base = f"《{title}》- {player_name}的旅程.zip"
        return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", base)

    def _build_story_script(
        self, package, play_state: dict, history_summary: str, player_name: str
    ) -> str:
        summary_section = history_summary.strip() or "（本段旅程暂未有可用的对话摘要。）"
        lines = [
            f"# 旅程回顾：{player_name}的《{package.title}》",
            "",
            "> 本文件为衍生剧本雏形，由游玩记录自动生成，供创作者继续编辑。",
            "",
            "## 游玩回顾",
            summary_section,
            "",
            "## 最终状态",
            "```json",
            json.dumps(play_state, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 场景模板",
            "（在此编写你的故事分支与脚本标记，例如：）",
            "",
            "[脚本: add_affection(target=\"butler\", amount=1)]",
            "",
            "**如果** affection.butler >= 3 **则**",
            "  管家露出微笑。",
            "**结束**",
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _copy_scripts(zf: zipfile.ZipFile, package) -> None:
        scripts_dir = package.root / "scripts"
        if not scripts_dir.is_dir():
            return
        for path in sorted(scripts_dir.rglob("*.py")):
            rel = path.relative_to(package.root)
            zf.write(path, rel.as_posix())