"""把 examples/demo_story 打包为 examples/demo_story.zip。"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORY = ROOT / "demo_story"
OUT = ROOT / "demo_story.zip"


def build() -> Path:
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(STORY.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(STORY))
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"已生成: {path} ({path.stat().st_size} bytes)")
    sys.exit(0)
