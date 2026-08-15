"""主窗口。"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QThread

from paotuan.config import AppConfig
from paotuan.censor import RemoteCensor
from paotuan.context import History, HistoryCompressor
from paotuan.generator import PlaythroughExporter
from paotuan.llm import LLMClient
from paotuan.loader import PackageSecurityError, load_package
from paotuan.state import StateManager
from paotuan.state.persistence import autosave_dir
from paotuan.workflow import Agent, NarrativeResult

from .input_bar import InputBar
from .library import pick_load_file, pick_save_file, pick_script
from .settings_dialog import SettingsDialog
from .state_panel import StatePanel
from .story_view import StoryView

logger = logging.getLogger(__name__)


class AgentWorker(QThread):
    """后台线程执行 Agent 单段闭环，避免阻塞 Qt 主线程。"""

    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(self, agent: Agent, text: str, parent=None, opening: bool = False):
        super().__init__(parent)
        self.agent = agent
        self.text = text
        self.opening = opening

    def run(self) -> None:  # noqa: D102
        try:
            if self.opening:
                result = self.agent.generate_opening()
            else:
                result = self.agent.handle_player_input(self.text)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("AgentWorker 异常")
            self.finished_error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.agent: Agent | None = None
        self.state: StateManager | None = None
        self.history: History | None = None
        self._loaded_package = None
        self._worker: AgentWorker | None = None
        self._opening_done = False
        self._save_dir: Path | None = None
        self._script_path: Path | None = None

        self.setWindowTitle("剧本跑团")
        self.resize(1000, 700)
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._maybe_show_risk_notice()

    def _maybe_show_risk_notice(self) -> None:
        """首次启动提示内容安全须知（一次，之后不再打扰）。"""
        if not self.config.show_risk_notice:
            return
        self.config.show_risk_notice = False
        self.config.save()
        QMessageBox.warning(
            self,
            "内容安全须知",
            "本平台的 AI 生成内容可能存在不可预知的风险，请勿依赖其提供的事实、法律或健康建议。\n"
            "如平台开启远程审查，建议在「设置 → API 配置」中勾选内容过滤以降低风险。",
        )

    # ------------------------------------------------------------- 界面构建
    def _build_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")
        act_open = QAction("打开剧本…", self)
        act_open.triggered.connect(self._on_open_script)
        file_menu.addAction(act_open)
        file_menu.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        game_menu = menubar.addMenu("游戏")
        self.act_save = QAction("存档…", self)
        self.act_save.triggered.connect(self._on_save)
        self.act_load = QAction("读档…", self)
        self.act_load.triggered.connect(self._on_load)
        self.act_export = QAction("导出旅程…", self)
        self.act_export.triggered.connect(self._on_export)
        game_menu.addAction(self.act_save)
        game_menu.addAction(self.act_load)
        game_menu.addSeparator()
        game_menu.addAction(self.act_export)
        self.act_save.setEnabled(False)
        self.act_load.setEnabled(False)
        self.act_export.setEnabled(False)

        settings_menu = menubar.addMenu("设置")
        act_settings = QAction("API 配置…", self)
        act_settings.triggered.connect(self._on_settings)
        settings_menu.addAction(act_settings)

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("配置")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.addWidget(QLabel("配置: "))
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("在已保存的 API 配置之间快速切换（同一服务商可保存多条）")
        tb.addWidget(self.profile_combo)
        self.profile_combo.activated.connect(self._on_profile_switch)
        self._sync_profile_combo()

    def _sync_profile_combo(self) -> None:
        self.profile_combo.clear()
        self.profile_combo.addItem("设置 API 配置…", "")
        for p in self.config.profiles or []:
            name = p.get("name") or p.get("provider") or "?"
            self.profile_combo.addItem(f"{name} · {p.get('provider')}", p.get("id"))
        if self.config.active_profile_id:
            idx = self.profile_combo.findData(self.config.active_profile_id)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)

    def _build_central(self) -> None:
        self.story_view = StoryView()
        self.state_panel = StatePanel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.story_view)
        splitter.addWidget(self.state_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self.input_bar = InputBar()
        self.input_bar.send_btn.clicked.connect(self._on_send)
        self.input_bar.edit.returnPressed.connect(self._on_send)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.input_bar)
        self.setCentralWidget(central)

        self.input_bar.setEnabled(False)
        self.story_view.append_system(
            "欢迎使用剧本跑团。请通过「文件 → 打开剧本…」加载剧本项目文件。"
        )

    # ------------------------------------------------------------- 剧本加载
    def _on_open_script(self) -> None:
        path = pick_script(self)
        if path is None:
            return
        self.load_script(path)

    def load_script(self, path: Path) -> None:
        try:
            package = load_package(path)
        except PackageSecurityError as exc:
            QMessageBox.critical(self, "加载失败", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "加载失败", f"未知错误: {exc}")
            return

        save_dir = autosave_dir(self.config.data_path, path)
        self._script_path = Path(path)
        self.state = StateManager(package.initial_state, autosave_path=save_dir / "state.json")
        self._loaded_package = package
        self._save_dir = save_dir
        resumed, history_msgs = self._restore_session()
        self.history = History()
        if history_msgs:
            self.history.messages = history_msgs
        self._opening_done = resumed and bool(self.history.messages)
        self._build_agent()
        self.setWindowTitle(f"剧本跑团 - {package.title}")
        self.story_view.clear()
        self.story_view.append_system(f"已加载剧本《{package.title}》（v{package.config.get('version', '?')}）")
        if resumed:
            self.story_view.append_system("已恢复上次游玩进度。")
            if not self.history.messages:
                self.story_view.append_system("上次会话记录不可用，将基于当前进度生成开场回顾。")
        for msg in self.history.messages:
            self.story_view.append_narrative(msg["content"], role=msg["role"])
        self.act_save.setEnabled(True)
        self.act_load.setEnabled(True)
        self.act_export.setEnabled(True)
        self.input_bar.setEnabled(self.config.configured)
        if not self.config.configured:
            self.story_view.append_system("提示：请先在「设置 → API 配置」填入 API Key。")
        self.state_panel.refresh(self.state.get())
        self.statusBar().showMessage(f"剧本: {package.title}", 5000)
        self._maybe_open_story()

    def _restore_session(self) -> tuple[bool, list[dict]]:
        """尝试从自动存档目录恢复上次游玩进度，返回 (是否恢复, 历史消息)。"""
        if self._save_dir is None:
            return False, []
        state_file = self._save_dir / "state.json"
        history_file = self._save_dir / "history.json"
        resumed = False
        history_msgs: list[dict] = []
        if state_file.exists():
            try:
                self.state.load(state_file)
                resumed = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("自动存档损坏，重新开始: %s", exc)
        if history_file.exists():
            try:
                saved = History()
                saved.load(history_file)
                history_msgs = saved.messages
            except Exception as exc:  # noqa: BLE001
                logger.warning("历史存档损坏，仅恢复状态: %s", exc)
        return resumed, history_msgs

    def _save_history(self) -> None:
        if self._save_dir is None or self.history is None or not self.history.messages:
            return
        try:
            self.history.save(self._save_dir / "history.json")
        except OSError:
            pass

    def _build_agent(self) -> None:
        if self.state is None or self._loaded_package is None:
            return
        llm = LLMClient(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            model=self.config.model,
            temperature=self.config.temperature,
            timeout=self.config.timeout,
            api_style=self.config.api_style,
        )
        self.agent = Agent(
            package=self._loaded_package,
            llm=llm,
            state=self.state,
            history=self.history or History(),
            intent_routing=self.config.intent_routing,
            compressor=(
                HistoryCompressor(llm) if self.config.context_compress else None
            ),
            remote_censor=(
                RemoteCensor(api_key=self.config.remote_censor_key)
                if self.config.remote_censor_enabled and self.config.remote_censor_key
                else None
            ),
        )

    # ------------------------------------------------------------- 交互
    def _on_send(self) -> None:
        text = self.input_bar.edit.text().strip()
        if not text or self.agent is None or self._worker is not None:
            return
        self.input_bar.edit.clear()
        self.input_bar.setEnabled(False)
        self.story_view.append_narrative(text, role="user")
        self._worker = AgentWorker(self.agent, text, self)
        self._worker.finished_ok.connect(self._on_result)
        self._worker.finished_error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_done)
        self.statusBar().showMessage("AI 正在思考…")
        self._worker.start()

    def _on_result(self, result: NarrativeResult) -> None:
        for msg in result.system_messages:
            self.story_view.append_system(msg)
        if result.ok:
            self.story_view.append_narrative(result.text)
        else:
            self.story_view.append_system(f"⚠ {result.error}")
        if self.state is not None:
            self.state_panel.refresh(self.state.get())
        self._save_history()

    def _on_error(self, message: str) -> None:
        self.story_view.append_system(f"⚠ 出错了: {message}")

    def _on_worker_done(self) -> None:
        self._worker = None
        self.input_bar.setEnabled(True)
        self.statusBar().clearMessage()

    def _on_save(self) -> None:
        if self.state is None:
            return
        path = pick_save_file(self)
        if path:
            try:
                saved = self.state.save(path)
                self.statusBar().showMessage(f"已存档: {saved}", 3000)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "存档失败", str(exc))

    def _on_load(self) -> None:
        if self.state is None:
            return
        path = pick_load_file(self)
        if path:
            try:
                self.state.load(path)
                self.state_panel.refresh(self.state.get())
                self.statusBar().showMessage(f"已读档: {path}", 3000)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "读档失败", str(exc))

    def _on_export(self) -> None:
        if self._loaded_package is None or self.state is None or not self._script_path:
            return
        out_dir = self.config.data_path / "exports"
        recap = self._history_recap()
        try:
            out = PlaythroughExporter().export(
                self._script_path,
                self.state.get(),
                history_summary=recap,
                output_dir=out_dir,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self.statusBar().showMessage(f"已导出衍生剧本: {out}", 5000)
        QMessageBox.information(self, "导出成功", f"已生成衍生剧本项目文件：\n{out}")

    def _history_recap(self) -> str:
        if self.history is None:
            return ""
        parts = [f"叙述者：{m['content']}" if m["role"] == "assistant" else f"玩家：{m['content']}"
                 for m in self.history.messages[-40:]]
        return "\n".join(parts)[:4000]

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self._sync_profile_combo()
            if self.agent is not None:
                self._build_agent()
            self.input_bar.setEnabled(self.agent is not None and self.config.configured)
            self._maybe_open_story()

    # ------------------------------------------------------------- 配置切换
    def _on_profile_switch(self, index: int) -> None:
        pid = self.profile_combo.itemData(index)
        if not pid:
            self._on_settings()
            return
        if self._worker is not None and self._worker.isRunning():
            self._sync_profile_combo()
            self.statusBar().showMessage("AI 正在处理，请稍后再切换配置。", 3000)
            return
        if pid == self.config.active_profile_id:
            return
        self.config.apply_profile(pid)
        self.config.save()  # 记住本次切换，下次启动仍用当前配置
        self._build_agent()
        self.input_bar.setEnabled(self.agent is not None and self.config.configured)
        self.statusBar().showMessage(
            f"已切换到 {self.profile_combo.itemText(index)}", 3000
        )

    # ------------------------------------------------------------- 开场引导
    def _maybe_open_story(self) -> None:
        if self._opening_done or self.agent is None or not self.config.configured:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self.input_bar.setEnabled(False)
        self.statusBar().showMessage("正在生成开场引导…")
        self._worker = AgentWorker(self.agent, "", self, opening=True)
        self._worker.finished_ok.connect(self._on_opening_done)
        self._worker.finished_error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    def _on_opening_done(self, result: NarrativeResult) -> None:
        self._opening_done = True
        self._on_result(result)

    def closeEvent(self, event) -> None:  # noqa: D102
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(3000)
        super().closeEvent(event)