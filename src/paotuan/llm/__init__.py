"""LLM 模型接入。"""

from .client import LLMClient, LLMError, friendly_error
from .presets import (
    CUSTOM_ID,
    PROVIDER_MAP,
    PROVIDERS,
    ProviderPreset,
    ModelPreset,
    detect_provider,
)
from .provider import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from .schemas import IntentResult, ScriptCallSpec

__all__ = [
    "LLMClient",
    "LLMError",
    "friendly_error",
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "CUSTOM_ID",
    "PROVIDER_MAP",
    "PROVIDERS",
    "ProviderPreset",
    "ModelPreset",
    "detect_provider",
    "IntentResult",
    "ScriptCallSpec",
]