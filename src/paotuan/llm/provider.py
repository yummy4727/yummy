"""LLM 提供商默认值（现由 presets 注册表提供）。"""

from __future__ import annotations

from .presets import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_TEMPERATURE

__all__ = ["DEFAULT_BASE_URL", "DEFAULT_MODEL", "DEFAULT_TEMPERATURE"]