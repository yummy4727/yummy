"""LLM 接入设置对话框：选服务商 → 选模型 → 粘贴 Key → 一键测试。"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from paotuan.config import AppConfig
from paotuan.llm import CUSTOM_ID, LLMClient, PROVIDER_MAP, PROVIDERS


class PingWorker(QThread):
    finished_ping = Signal(bool, str)

    def __init__(self, client: LLMClient, parent=None):
        super().__init__(parent)
        self.client = client

    def run(self) -> None:  # noqa: D102
        ok, msg = self.client.ping()
        self.finished_ping.emit(ok, msg)


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._worker: PingWorker | None = None
        self._last_provider: str | None = None
        # 对话框内按服务商暂存表单（切换服务商不丢已填内容）
        self._form_state: dict[str, dict] = {}
        self.setWindowTitle("设置 - LLM 接入")
        self.setMinimumWidth(460)

        form = QFormLayout()

        self.provider_combo = QComboBox()
        for p in PROVIDERS:
            self.provider_combo.addItem(p.name, p.id)
        form.addRow("服务商", self.provider_combo)

        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("同一服务商可保存多条 API 配置（多 Key/多账号）")
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        form.addRow("已保存配置", self.profile_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：DeepSeek 工作号 / DeepSeek 个人号")
        form.addRow("配置名称", self.name_edit)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        form.addRow("模型", self.model_combo)

        self.base_url_edit = QLineEdit()
        form.addRow("接口地址", self.base_url_edit)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key", self.api_key_edit)

        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        form.addRow("温度", self.temperature)

        # ------------------------------------------------------- M2 可选增强
        self.intent_chk = QCheckBox("两段式意图路由：LLM 拆解玩家意图后触发脚本")
        form.addRow("意图路由", self.intent_chk)

        self.compress_chk = QCheckBox("历史过长时用 LLM 摘要压缩（推荐开启）")
        form.addRow("记忆压缩", self.compress_chk)

        self.remote_chk = QCheckBox("开启 OpenAI Moderation 兼容远程审查")
        form.addRow("远程审查", self.remote_chk)

        self.remote_key_edit = QLineEdit()
        self.remote_key_edit.setEchoMode(QLineEdit.Password)
        self.remote_key_edit.setPlaceholderText("sk-...（审核服务 Key）")
        self.remote_chk.toggled.connect(self.remote_key_edit.setEnabled)
        form.addRow("审查 Key", self.remote_key_edit)

        self.key_tip = QLabel()
        self.key_tip.setOpenExternalLinks(True)
        self.key_tip.setWordWrap(True)
        form.addRow("", self.key_tip)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        form.addRow("", self.status)

        self._populate_from_config()
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        buttons = QDialogButtonBox()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._on_test)
        buttons.addButton(self.test_btn, QDialogButtonBox.ActionRole)
        self.ok_btn = buttons.addButton(QDialogButtonBox.Ok)
        self.cancel_btn = buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    # ------------------------------------------------------------- 状态恢复
    def _populate_from_config(self) -> None:
        idx = self.provider_combo.findData(self.config.provider)
        if idx < 0:
            idx = self.provider_combo.findData(CUSTOM_ID)
        self.provider_combo.setCurrentIndex(max(idx, 0))
        self._last_provider = self._current_preset().id
        self._rebuild_for_provider(initial=True)

    def _on_provider_changed(self) -> None:
        # 先把当前服务商表单存起来，再按新服务商重建
        prev = self._last_provider
        if prev:
            self._form_state[prev] = {
                "api_key": self.api_key_edit.text().strip(),
                "model": self._stash_model_value(),
                "temperature": self.temperature.value(),
                "profile_id": self.profile_combo.currentData() or "",
                "name": self.name_edit.text().strip(),
            }
        self._rebuild_for_provider()
        self._last_provider = self._current_preset().id

    def _stash_model_value(self) -> str:
        """取当前模型值：选中项且未改动文本 → id；否则返回（手输的）文本。"""
        le = self.model_combo.lineEdit()
        if le is not None:
            edit_text = le.text().strip()
            if edit_text and self.model_combo.currentIndex() < 0:
                return edit_text
        idx = self.model_combo.currentIndex()
        data = self.model_combo.itemData(idx)
        if data and self.model_combo.currentText() == self.model_combo.itemText(idx):
            return str(data)
        return self.model_combo.currentText().strip()

    def _rebuild_for_provider(self, initial: bool = False) -> None:
        preset = self._current_preset()

        # 已保存配置下拉（blockSignals：避免重建时误触发 _on_profile_selected）
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("＋ 新建配置", "")
        for p in self.config.profiles_for(preset.id):
            self.profile_combo.addItem(p.get("name") or preset.id, p.get("id"))
        self.profile_combo.blockSignals(False)

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for m in preset.models:
            self.model_combo.addItem(m.label, m.id)
        self.model_combo.blockSignals(False)

        if preset.base_url:
            self.base_url_edit.setText(preset.base_url)
            self.base_url_edit.setPlaceholderText(preset.base_url)
        else:
            self.base_url_edit.setText(self.config.base_url or "")
            self.base_url_edit.setPlaceholderText("https://api.example.com/v1")

        self.api_key_edit.setPlaceholderText("sk-...（粘贴你的 API Key）")
        if preset.key_tip:
            self.key_tip.setText(
                f'Key 获取入口：<a href="{preset.key_tip}">{preset.key_tip}</a>'
            )
        else:
            self.key_tip.setText("填写任意 OpenAI 兼容接口的地址与 Key。")

        # 表单取值：本次会话草稿优先，其次已保存/当前生效配置
        if not initial:
            state = self._form_state.get(preset.id)
            entry = state or next(iter(self.config.profiles_for(preset.id)), {})
        else:
            active = self.config.active_profile()
            if active.get("provider") == preset.id:
                entry = active
            else:
                entry = {
                    "api_key": self.config.api_key,
                    "model": self.config.model,
                    "temperature": self.config.temperature,
                }

        profile_id = entry.get("id", "") if entry else ""
        api_key = entry.get("api_key", "")
        model = entry.get("model", "")
        temperature = entry.get("temperature", self.config.temperature)

        self.profile_combo.blockSignals(True)
        if profile_id and self.profile_combo.findData(profile_id) >= 0:
            self.profile_combo.setCurrentIndex(self.profile_combo.findData(profile_id))
        else:
            self.profile_combo.setCurrentIndex(0)  # ＋ 新建配置
        self.profile_combo.blockSignals(False)

        self.name_edit.setText(entry.get("name", "") if entry else "")

        if model:
            idx = self.model_combo.findData(model)
            if idx < 0:
                idx = self.model_combo.findText(model)  # 允许按显示标签恢复
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                self.model_combo.setEditText(model)
        elif self.model_combo.count():
            self.model_combo.setCurrentIndex(0)

        self.api_key_edit.setText(api_key)
        self.temperature.setValue(
            float(temperature) if temperature is not None else self.config.temperature
        )
        self.intent_chk.setChecked(self.config.intent_routing)
        self.compress_chk.setChecked(self.config.context_compress)
        self.remote_chk.setChecked(self.config.remote_censor_enabled)
        self.remote_key_edit.setText(self.config.remote_censor_key)
        self.remote_key_edit.setEnabled(self.config.remote_censor_enabled)
        self._on_model_changed()
        self.status.setText("")

    def _on_profile_selected(self) -> None:
        """用户手动选择「已保存配置」：加载该配置到表单。"""
        pid = self.profile_combo.currentData()
        preset = self._current_preset()
        if not pid:
            # ＋ 新建配置：清空 Key 与名称，保留服务商默认模型/地址
            self.api_key_edit.setText("")
            self.name_edit.setText("")
            if self.model_combo.count() and self.model_combo.currentIndex() < 0:
                self.model_combo.setCurrentIndex(0)
            self._on_model_changed()
            return
        entry = self.config.get_profile(pid)
        if not entry:
            return
        self.name_edit.setText(entry.get("name", ""))
        self.api_key_edit.setText(entry.get("api_key", ""))
        model = entry.get("model", "")
        if model:
            idx = self.model_combo.findData(model)
            if idx < 0:
                idx = self.model_combo.findText(model)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                self.model_combo.setEditText(model)
        self.temperature.setValue(
            float(entry.get("temperature", self.config.temperature))
        )
        self._on_model_changed()

    def _on_model_changed(self) -> None:
        # 某些模型走专用端点：切换模型时刷新接口地址
        preset = self._current_preset()
        mp = self._current_model_preset(preset)
        if mp and mp.base_url:
            self.base_url_edit.setText(mp.base_url)
            self.base_url_edit.setPlaceholderText(mp.base_url)
        elif preset.base_url:
            self.base_url_edit.setText(preset.base_url)

    def _current_preset(self):
        pid = self.provider_combo.currentData()
        return PROVIDER_MAP.get(pid, PROVIDER_MAP[CUSTOM_ID])

    def _current_model_preset(self, preset):
        if preset.id == CUSTOM_ID or self.model_combo.count() == 0:
            return None
        idx = self.model_combo.currentIndex()
        if idx < 0:
            return None
        mid = self.model_combo.itemData(idx)
        for m in preset.models:
            if m.id == mid:
                return m
        return None

    def _effective_api_style(self, preset) -> str:
        mp = self._current_model_preset(preset)
        if mp and mp.api_style:
            return mp.api_style
        return preset.api_style

    def _current_model(self) -> str:
        # 可编辑下拉框：选中项且未改动文本 → 取 data（模型 id）；
        # 手输文本与选中项不一致 → 以手输文本为准。
        le = self.model_combo.lineEdit()
        edit_text = le.text().strip() if le is not None else ""
        idx = self.model_combo.currentIndex()
        data = self.model_combo.itemData(idx)
        if data and edit_text == self.model_combo.itemText(idx):
            return str(data)
        if edit_text:
            return edit_text
        if idx >= 0 and data:
            return str(data)
        return self.model_combo.currentText().strip()

    # ------------------------------------------------------------- 测试连接
    def _on_test(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not self.api_key_edit.text().strip():
            self.status.setText("请先粘贴 API Key 再测试。")
            return
        client = self._build_client_from_form()
        self.test_btn.setEnabled(False)
        self.status.setText("正在连接…")
        self._worker = PingWorker(client, self)
        self._worker.finished_ping.connect(self._on_ping_done)
        self._worker.start()

    def _on_ping_done(self, ok: bool, msg: str) -> None:
        self._worker = None
        self.test_btn.setEnabled(True)
        if ok:
            self.status.setStyleSheet("color: #2e7d32;")
            self.status.setText(msg)
        else:
            self.status.setStyleSheet("color: #c62828;")
            self.status.setText(msg)
            QMessageBox.warning(self, "连接失败", msg)

    # ------------------------------------------------------------- 提交
    def _build_client_from_form(self) -> LLMClient:
        preset = self._current_preset()
        base_url = self.base_url_edit.text().strip() or preset.base_url
        return LLMClient(
            base_url=base_url,
            api_key=self.api_key_edit.text().strip(),
            model=self._current_model(),
            temperature=self.temperature.value(),
            api_style=self._effective_api_style(preset),
        )

    def _accept(self) -> None:
        preset = self._current_preset()
        model = self._current_model()
        if not model:
            QMessageBox.warning(self, "缺少模型", "请选择或输入模型名称。")
            return
        if not self.api_key_edit.text().strip():
            QMessageBox.warning(self, "缺少 Key", "请粘贴 API Key。")
            return

        base_url = self.base_url_edit.text().strip() or preset.base_url
        name = self.name_edit.text().strip() or preset.name
        self.config.intent_routing = self.intent_chk.isChecked()
        self.config.context_compress = self.compress_chk.isChecked()
        self.config.remote_censor_enabled = self.remote_chk.isChecked()
        self.config.remote_censor_key = self.remote_key_edit.text().strip()
        pid = self.profile_combo.currentData() or None  # 选中的既有配置或新建
        self.config.save_profile(
            provider=preset.id,
            api_key=self.api_key_edit.text().strip(),
            model=model,
            temperature=self.temperature.value(),
            base_url=base_url,
            api_style=self._effective_api_style(preset),
            name=name,
            profile_id=pid,
        )
        self.accept()