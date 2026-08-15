"""应用配置：LLM 接入信息与本地数据目录。"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from paotuan.llm.presets import CUSTOM_ID, DEFAULT_MODEL, PROVIDER_MAP, detect_provider


def _default_data_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "paotuan"


@dataclass
class AppConfig:
    """应用级配置。API Key 等敏感信息仅保存在本地。"""

    provider: str = "deepseek"
    api_style: str = "openai"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.8
    timeout: float = 60.0
    data_dir: str = field(default_factory=lambda: str(_default_data_dir()))
    # M2：两段式意图路由（LLM 拆解玩家意图替代 M1 规则触发）
    intent_routing: bool = False
    # M2：记忆压缩（历史超长时 LLM 摘要）
    context_compress: bool = True
    # M2：可选远程审查（OpenAI Moderation 兼容接口）
    remote_censor_enabled: bool = False
    remote_censor_key: str = ""
    # 命名 API 配置列表；同一服务商可保存多个（多 Key/多账号）
    profiles: list[dict] = field(default_factory=list)
    # 当前生效的是哪条命名配置（"" 表示未关联）
    active_profile_id: str = ""
    # 首次启动是否已提示过内容安全须知（AI 生成内容存在不可预知风险）
    show_risk_notice: bool = True

    def __post_init__(self) -> None:
        # 载入旧配置或手工构造时，按 provider 补齐默认值
        preset = PROVIDER_MAP.get(self.provider)
        if preset:
            if not self.base_url:
                self.base_url = preset.base_url
            if not self.model and preset.models:
                self.model = preset.models[0].id
            if preset.api_style:
                self.api_style = preset.api_style
            # 兜底：历史配置误存了显示标签时，还原为模型 id
            if self.model:
                for m in preset.models:
                    if self.model == m.label:
                        self.model = m.id
                        break
        self._normalize_profiles()

    def _normalize_profiles(self) -> None:
        # 兼容旧版 {provider: {...}} dict 格式
        if isinstance(self.profiles, dict):
            entries = []
            for pid, p in self.profiles.items():
                preset = PROVIDER_MAP.get(pid)
                entries.append(
                    {
                        "id": pid,
                        "name": preset.name if preset else pid,
                        "provider": pid,
                        "api_key": p.get("api_key", ""),
                        "model": p.get("model", ""),
                        "temperature": p.get("temperature", self.temperature),
                        "base_url": p.get("base_url", ""),
                        "api_style": p.get("api_style", ""),
                    }
                )
            self.profiles = entries
        for i, entry in enumerate(self.profiles or []):
            if not isinstance(entry, dict):
                continue
            if not entry.get("id"):
                entry["id"] = f"profile-{i}"
            if not entry.get("name"):
                preset = PROVIDER_MAP.get(entry.get("provider"))
                entry["name"] = (
                    preset.name
                    if preset
                    else (entry.get("provider") or f"配置 {i + 1}")
                )

    @staticmethod
    def _new_profile_id() -> str:
        return "p-" + uuid.uuid4().hex[:8]

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    def config_file(self) -> Path:
        return self.data_path / "config.json"

    def save(self) -> None:
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.config_file().write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls) -> "AppConfig":
        cfg = cls()
        path = cfg.config_file()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return cfg
            had_provider = "provider" in data
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
            if not had_provider:
                cfg._migrate_from_legacy()
        cfg.__post_init__()
        return cfg

    def _migrate_from_legacy(self) -> None:
        """旧版配置没有 provider 字段：按 base_url 反推服务商。"""
        detected = detect_provider(self.base_url) if self.base_url else None
        if detected:
            self.provider = detected
        else:
            self.provider = CUSTOM_ID
        preset = PROVIDER_MAP.get(self.provider)
        if preset and preset.api_style:
            self.api_style = preset.api_style

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def profiles_for(self, provider: str) -> list[dict]:
        """某服务商下的所有命名配置（可为多个）。"""
        return [p for p in (self.profiles or []) if p.get("provider") == provider]

    def get_profile(self, profile_id: str) -> dict:
        """按 id 取命名配置（空 dict 表示不存在）。"""
        for p in self.profiles or []:
            if p.get("id") == profile_id:
                return dict(p)
        return {}

    def active_profile(self) -> dict:
        """当前生效的命名配置（未关联则取当前服务商的最后一条）。"""
        if self.active_profile_id:
            entry = self.get_profile(self.active_profile_id)
            if entry:
                return entry
        for p in reversed(self.profiles_for(self.provider)):
            return dict(p)
        return {}

    def save_profile(
        self,
        provider: str,
        api_key: str,
        model: str,
        temperature: float,
        base_url: str = "",
        api_style: str = "",
        name: str = "",
        profile_id: str | None = None,
    ) -> str:
        """保存（或覆盖）一条命名配置并设为当前生效，返回其 id。

        同一服务商可保存多条：不传 profile_id 即新建。
        """
        preset = PROVIDER_MAP.get(provider)
        if not name:
            name = preset.name if preset else provider
        updates = {
            "name": name,
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "temperature": temperature,
            "base_url": base_url,
            "api_style": api_style,
        }
        if profile_id and self.get_profile(profile_id):
            for p in self.profiles:
                if p.get("id") == profile_id:
                    p.update(updates)
                    break
        else:
            entry = {"id": self._new_profile_id(), "provider": provider}
            entry.update(updates)
            self.profiles.append(entry)
            profile_id = entry["id"]
        # 设为当前生效配置
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.base_url = base_url or (preset.base_url if preset else "")
        self.api_style = api_style or (preset.api_style if preset else "openai")
        self.active_profile_id = profile_id
        self.save()
        return profile_id

    def apply_profile(self, profile_id: str) -> bool:
        """把某条命名配置应用为当前配置（不落盘，由调用方决定）。"""
        entry = self.get_profile(profile_id)
        if not entry:
            return False
        preset = PROVIDER_MAP.get(entry["provider"])
        self.provider = entry["provider"]
        self.base_url = entry.get("base_url") or (preset.base_url if preset else "")
        self.api_style = entry.get("api_style") or (
            preset.api_style if preset else "openai"
        )
        self.model = entry.get("model") or (
            preset.models[0].id if preset and preset.models else ""
        )
        self.api_key = entry.get("api_key", "")
        self.temperature = float(entry.get("temperature", self.temperature))
        self.active_profile_id = entry["id"]
        return True
