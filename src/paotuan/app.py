"""应用装配：配置 → 主窗口。"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from paotuan.config import AppConfig
from paotuan.loader import PackageSecurityError
from paotuan.ui.main_window import MainWindow


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="paotuan", description="剧本跑团客户端")
    parser.add_argument("--script", help="启动时直接加载的剧本项目文件（.zip）")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    _setup_logging()
    args = parse_args(argv)
    config = AppConfig.load()

    app = QApplication(sys.argv[:1])
    window = MainWindow(config)
    window.show()

    if args.script:
        path = Path(args.script)
        if not path.is_file():
            QMessageBox.critical(window, "加载失败", f"剧本文件不存在: {path}")
        else:
            window.load_script(path)

    return app.exec()


def main() -> None:
    sys.exit(run())