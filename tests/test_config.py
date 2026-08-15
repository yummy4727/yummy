"""config：默认值、旧配置迁移、服务商联动。"""

from __future__ import annotations

import json

from paotuan.config import AppConfig


def _patch_data_dir(monkeypatch, tmp_path) -> None:
    import paotuan.config as cfgmod

    monkeypatch.setattr(cfgmod, "_default_data_dir", lambda: tmp_path / "data")


def test_defaults_match_deepseek():
    cfg = AppConfig()
    assert cfg.provider == "deepseek"
    assert cfg.base_url == "https://api.deepseek.com"
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.api_style == "openai"


def test_load_migrates_legacy_openai(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg_path = tmp_path / "data" / "config.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        json.dumps(
            {
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-legacy",
                "model": "gpt-4o",
                "temperature": 0.5,
            }
        ),
        encoding="utf-8",
    )
    cfg = AppConfig.load()
    assert cfg.provider == "openai"
    assert cfg.api_style == "openai"
    assert cfg.base_url == "https://api.openai.com/v1"
    assert cfg.model == "gpt-4o"
    assert cfg.api_key == "sk-legacy"


def test_load_migrates_legacy_custom(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg_path = tmp_path / "data" / "config.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        json.dumps({"base_url": "https://mygw.example.com/v1", "api_key": "k"}),
        encoding="utf-8",
    )
    cfg = AppConfig.load()
    assert cfg.provider == "custom"
    assert cfg.base_url == "https://mygw.example.com/v1"
    assert cfg.api_style == "openai"


def test_save_load_roundtrip(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg = AppConfig()
    cfg.api_key = "sk-123"
    cfg.provider = "anthropic"
    cfg.api_style = "anthropic"
    cfg.base_url = "https://api.anthropic.com"
    cfg.model = "claude-sonnet-4-20250514"
    cfg.save()

    loaded = AppConfig.load()
    assert loaded.provider == "anthropic"
    assert loaded.api_style == "anthropic"
    assert loaded.model == "claude-sonnet-4-20250514"
    assert loaded.api_key == "sk-123"


def test_load_normalizes_model_label_to_id(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg_path = tmp_path / "data" / "config.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        json.dumps(
            {
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-1",
                "model": "DeepSeek-V4-Flash · 默认推荐",
            }
        ),
        encoding="utf-8",
    )
    cfg = AppConfig.load()
    assert cfg.model == "deepseek-v4-flash"


def test_configured_requires_key():
    assert not AppConfig().configured
    cfg = AppConfig()
    cfg.api_key = " "
    assert not cfg.configured
    cfg.api_key = "sk-1"
    assert cfg.configured


def test_save_profile_persists_and_applies(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg = AppConfig()
    pid = cfg.save_profile(
        provider="kimi",
        api_key="sk-kimi",
        model="kimi-k3",
        temperature=0.3,
        base_url="https://api.moonshot.ai/v1",
        api_style="openai",
    )
    assert pid
    assert cfg.provider == "kimi"
    assert cfg.api_key == "sk-kimi"
    assert cfg.model == "kimi-k3"
    assert cfg.temperature == 0.3
    assert cfg.base_url == "https://api.moonshot.ai/v1"
    assert cfg.active_profile_id == pid

    loaded = AppConfig.load()
    entry = loaded.get_profile(pid)
    assert entry["api_key"] == "sk-kimi"
    assert entry["model"] == "kimi-k3"
    assert entry["temperature"] == 0.3
    assert entry["base_url"] == "https://api.moonshot.ai/v1"
    assert entry["name"]  # 未传名称时默认用服务商名


def test_multiple_profiles_same_provider(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg = AppConfig()
    pid1 = cfg.save_profile(
        provider="deepseek", api_key="sk-work", model="deepseek-v4-pro",
        temperature=0.5, name="DeepSeek 工作号",
    )
    pid2 = cfg.save_profile(
        provider="deepseek", api_key="sk-personal", model="deepseek-v4-flash",
        temperature=0.2, name="DeepSeek 个人号",
    )
    assert pid1 != pid2
    entries = cfg.profiles_for("deepseek")
    assert [e["id"] for e in entries] == [pid1, pid2]
    assert cfg.api_key == "sk-personal"  # 最后保存的为当前生效

    cfg.apply_profile(pid1)
    assert cfg.api_key == "sk-work"
    assert cfg.model == "deepseek-v4-pro"
    assert cfg.temperature == 0.5
    assert cfg.active_profile_id == pid1

    cfg.apply_profile(pid2)
    assert cfg.api_key == "sk-personal"
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.temperature == 0.2
    assert cfg.active_profile_id == pid2


def test_save_profile_overwrites_existing(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg = AppConfig()
    pid = cfg.save_profile(
        provider="qwen", api_key="sk-a", model="qwen3.7-max", temperature=0.9,
        name="通义主号",
    )
    cfg.save_profile(
        provider="qwen", api_key="sk-b", model="qwen3.7-plus", temperature=0.7,
        name="通义主号", profile_id=pid,
    )
    assert len(cfg.profiles_for("qwen")) == 1
    assert cfg.profiles_for("qwen")[0]["api_key"] == "sk-b"


def test_apply_profile_unconfigured_uses_default_model(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg = AppConfig()
    pid = cfg.save_profile(
        provider="opencode", api_key="", model="", temperature=0.8,
    )
    cfg.apply_profile(pid)
    assert cfg.provider == "opencode"
    assert cfg.api_key == ""
    assert cfg.model == "deepseek-v4-pro"  # 预设默认模型


def test_load_migrates_legacy_profiles_dict(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    cfg_path = tmp_path / "data" / "config.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        json.dumps(
            {
                "provider": "kimi",
                "base_url": "https://api.moonshot.ai/v1",
                "api_key": "sk-old",
                "model": "kimi-k2.6",
                "profiles": {
                    "kimi": {
                        "api_key": "sk-k",
                        "model": "kimi-k3",
                        "temperature": 0.3,
                        "base_url": "https://api.moonshot.ai/v1",
                        "api_style": "openai",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = AppConfig.load()
    entries = cfg.profiles_for("kimi")
    assert len(entries) == 1
    assert entries[0]["id"] == "kimi"
    assert entries[0]["api_key"] == "sk-k"
    assert entries[0]["model"] == "kimi-k3"
    assert entries[0]["name"]