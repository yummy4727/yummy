"""主流模型服务商预设注册表。

每种服务商预置：接入地址、鉴权方式、可用模型列表与获取 Key 的入口。
用户在设置中只需：选服务商 → 选模型 → 粘贴 API Key。
"""

from __future__ import annotations

from dataclasses import dataclass, field

CUSTOM_ID = "custom"

# 鉴权/请求风格
STYLE_OPENAI = "openai"  # Authorization: Bearer + POST /chat/completions
STYLE_ANTHROPIC = "anthropic"  # x-api-key + POST /v1/messages


@dataclass(frozen=True)
class ModelPreset:
    id: str
    label: str
    base_url: str | None = None  # 覆盖服务商默认接口地址（某些模型走专用端点）
    api_style: str | None = None  # 覆盖请求风格（如个别模型走 Anthropic 兼容端点）


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    name: str
    base_url: str
    key_tip: str = ""
    api_style: str = STYLE_OPENAI
    models: tuple[ModelPreset, ...] = ()


PROVIDERS: list[ProviderPreset] = [
    ProviderPreset(
        id="deepseek",
        name="DeepSeek 深度求索",
        base_url="https://api.deepseek.com",
        key_tip="https://platform.deepseek.com",
        models=(
            ModelPreset("deepseek-v4-flash", "DeepSeek-V4-Flash · 默认推荐"),
            ModelPreset("deepseek-v4-pro", "DeepSeek-V4-Pro · 旗舰推理"),
        ),
    ),
    ProviderPreset(
        id="opencode",
        name="OpenCode Zen（多模型聚合）",
        base_url="https://opencode.ai/zen/v1",
        key_tip="https://opencode.ai/auth",
        models=(
            ModelPreset("deepseek-v4-pro", "DeepSeek V4 Pro"),
            ModelPreset("deepseek-v4-flash", "DeepSeek V4 Flash"),
            ModelPreset("deepseek-v4-flash-free", "DeepSeek V4 Flash Free · 免费"),
            ModelPreset("kimi-k3", "Kimi K3"),
            ModelPreset("kimi-k2.7-code", "Kimi K2.7 Code"),
            ModelPreset("glm-5.3", "GLM 5.3"),
            ModelPreset("glm-5.2", "GLM 5.2"),
            ModelPreset("qwen3.8-max", "Qwen3.8-Max"),
            ModelPreset("minimax-m3", "MiniMax M3"),
            ModelPreset("gpt-5.6-luna", "GPT-5.6 Luna"),
            ModelPreset("grok-4.5", "Grok 4.5"),
        ),
    ),
    ProviderPreset(
        id="opencode-go",
        name="OpenCode Go（月卡订阅）",
        base_url="https://opencode.ai/zen/go/v1",
        key_tip="https://opencode.ai/auth",
        models=(
            ModelPreset("deepseek-v4-pro", "DeepSeek V4 Pro"),
            ModelPreset("deepseek-v4-flash", "DeepSeek V4 Flash"),
            ModelPreset("kimi-k3", "Kimi K3"),
            ModelPreset("kimi-k2.7-code", "Kimi K2.7 Code"),
            ModelPreset("kimi-k2.6", "Kimi K2.6"),
            ModelPreset("kimi-k2.5", "Kimi K2.5"),
            ModelPreset("glm-5.3", "GLM 5.3"),
            ModelPreset("glm-5.2", "GLM 5.2"),
            ModelPreset("glm-5.1", "GLM 5.1"),
            ModelPreset("glm-5", "GLM 5"),
            ModelPreset("qwen3.8-max", "Qwen3.8-Max"),
            ModelPreset("qwen3.7-max", "Qwen3.7-Max"),
            ModelPreset("qwen3.7-plus", "Qwen3.7-Plus"),
            ModelPreset("qwen3.6-plus", "Qwen3.6-Plus"),
            ModelPreset("qwen3.5-plus", "Qwen3.5-Plus"),
            ModelPreset("minimax-m3", "MiniMax M3"),
            ModelPreset("minimax-m2.7", "MiniMax M2.7"),
            ModelPreset("minimax-m2.5", "MiniMax M2.5"),
            ModelPreset("gpt-5.6-luna", "GPT-5.6 Luna"),
            ModelPreset("grok-4.5", "Grok 4.5"),
            ModelPreset("mimo-v2.5-pro", "MiMo V2.5 Pro"),
            ModelPreset("mimo-v2.5", "MiMo V2.5"),
            ModelPreset("mimo-v2-pro", "MiMo V2 Pro"),
            ModelPreset("mimo-v2-omni", "MiMo V2 Omni"),
            ModelPreset("hy3", "Hy3"),
            ModelPreset("hy3-preview", "Hy3 Preview"),
        ),
    ),
    ProviderPreset(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        key_tip="https://platform.openai.com/api-keys",
        models=(
            ModelPreset("gpt-5.6-sol", "GPT-5.6 Sol · 旗舰"),
            ModelPreset("gpt-5.6-terra", "GPT-5.6 Terra · 均衡"),
            ModelPreset("gpt-5.6-luna", "GPT-5.6 Luna · 低成本"),
            ModelPreset("gpt-5.5", "GPT-5.5"),
        ),
    ),
    ProviderPreset(
        id="kimi",
        name="Kimi 月之暗面",
        base_url="https://api.moonshot.ai/v1",
        key_tip="https://platform.kimi.ai",
        models=(
            ModelPreset("kimi-k3", "Kimi K3 · 旗舰 1M 上下文"),
            ModelPreset("kimi-k2.7-code", "Kimi K2.7 Code · 编程"),
            ModelPreset("kimi-k2.7-code-highspeed", "Kimi K2.7 Code · 高速版"),
            ModelPreset("kimi-k2.6", "Kimi K2.6 · 通用思考"),
        ),
    ),
    ProviderPreset(
        id="zhipu",
        name="智谱 GLM（BigModel）",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        key_tip="https://open.bigmodel.cn",
        models=(
            ModelPreset("glm-5.3", "GLM-5.3 · 旗舰"),
            ModelPreset("glm-5.2", "GLM-5.2 · 长上下文"),
            ModelPreset("glm-5.1", "GLM-5.1"),
            ModelPreset("glm-5", "GLM-5"),
            ModelPreset("glm-4.7-flash", "GLM-4.7-Flash · 免费档"),
            ModelPreset("glm-4.5-air", "GLM-4.5-Air · 高性价比"),
        ),
    ),
    ProviderPreset(
        id="qwen",
        name="通义千问（阿里云百炼）",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        key_tip="https://bailian.console.aliyun.com",
        models=(
            ModelPreset("qwen3.8-max", "Qwen3.8-Max · 旗舰"),
            ModelPreset("qwen3.7-max", "Qwen3.7-Max"),
            ModelPreset("qwen3.7-plus", "Qwen3.7-Plus · 高性价比"),
            ModelPreset("qwen3.7-flash", "Qwen3.7-Flash · 快速"),
            ModelPreset("qwen-plus", "Qwen-Plus · 稳定别名"),
            ModelPreset("qwen-flash", "Qwen-Flash · 快速别名"),
            ModelPreset("qwen3-coder-plus", "Qwen3-Coder-Plus"),
        ),
    ),
    ProviderPreset(
        id="siliconflow",
        name="SiliconFlow 硅基流动（多模型）",
        base_url="https://api.siliconflow.cn/v1",
        key_tip="https://cloud.siliconflow.cn/account/ak",
        models=(
            # DeepSeek
            ModelPreset("deepseek-ai/DeepSeek-V4-Pro", "DeepSeek-V4-Pro · 旗舰"),
            ModelPreset("deepseek-ai/DeepSeek-V4-Flash", "DeepSeek-V4-Flash · 预览"),
            ModelPreset("deepseek-ai/DeepSeek-V3.2", "DeepSeek-V3.2"),
            ModelPreset("deepseek-ai/DeepSeek-V3.1-Terminus", "DeepSeek-V3.1-Terminus"),
            ModelPreset("deepseek-ai/DeepSeek-V3", "DeepSeek-V3"),
            ModelPreset("deepseek-ai/DeepSeek-R1", "DeepSeek-R1 · 推理"),
            ModelPreset("deepseek-ai/DeepSeek-R1-0528-Qwen3-8B", "DeepSeek-R1-0528-Qwen3-8B"),
            ModelPreset("Pro/deepseek-ai/DeepSeek-V3.2", "Pro DeepSeek-V3.2"),
            ModelPreset("Pro/deepseek-ai/DeepSeek-V3.1-Terminus", "Pro DeepSeek-V3.1-Terminus"),
            ModelPreset("Pro/deepseek-ai/DeepSeek-V3", "Pro DeepSeek-V3"),
            ModelPreset("Pro/deepseek-ai/DeepSeek-R1", "Pro DeepSeek-R1"),
            # GLM / 智谱
            ModelPreset("zai-org/GLM-5.2", "GLM-5.2"),
            ModelPreset("Pro/zai-org/GLM-5.1", "Pro GLM-5.1"),
            ModelPreset("zai-org/GLM-4.5-Air", "GLM-4.5-Air · 轻量"),
            ModelPreset("THUDM/GLM-4-32B-0414", "GLM-4-32B-0414"),
            ModelPreset("THUDM/GLM-4-9B-0414", "GLM-4-9B-0414"),
            ModelPreset("THUDM/GLM-Z1-9B-0414", "GLM-Z1-9B-0414"),
            # Qwen / 通义
            ModelPreset("Qwen/Qwen3.6-35B-A3B", "Qwen3.6-35B-A3B"),
            ModelPreset("Qwen/Qwen3.6-27B", "Qwen3.6-27B"),
            ModelPreset("Qwen/Qwen3.5-397B-A17B", "Qwen3.5-397B-A17B"),
            ModelPreset("Qwen/Qwen3.5-122B-A10B", "Qwen3.5-122B-A10B"),
            ModelPreset("Qwen/Qwen3.5-35B-A3B", "Qwen3.5-35B-A3B"),
            ModelPreset("Qwen/Qwen3.5-27B", "Qwen3.5-27B"),
            ModelPreset("Qwen/Qwen3.5-9B", "Qwen3.5-9B"),
            ModelPreset("Qwen/Qwen3.5-4B", "Qwen3.5-4B"),
            ModelPreset("Qwen/Qwen3-32B", "Qwen3-32B"),
            ModelPreset("Qwen/Qwen3-14B", "Qwen3-14B"),
            ModelPreset("Qwen/Qwen3-8B", "Qwen3-8B"),
            ModelPreset("Qwen/Qwen3-30B-A3B-Instruct-2507", "Qwen3-30B-A3B-Instruct-2507"),
            ModelPreset("Qwen/Qwen3-Coder-30B-A3B-Instruct", "Qwen3-Coder-30B-A3B-Instruct"),
            ModelPreset("Qwen/Qwen2.5-72B-Instruct-128K", "Qwen2.5-72B-Instruct-128K"),
            ModelPreset("Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B-Instruct"),
            ModelPreset("Qwen/Qwen2.5-32B-Instruct", "Qwen2.5-32B-Instruct"),
            ModelPreset("Qwen/Qwen2.5-14B-Instruct", "Qwen2.5-14B-Instruct"),
            ModelPreset("Qwen/Qwen2.5-7B-Instruct", "Qwen2.5-7B-Instruct"),
            ModelPreset("Pro/Qwen/Qwen2.5-7B-Instruct", "Pro Qwen2.5-7B-Instruct"),
            # Kimi / 月之暗面
            ModelPreset("moonshotai/Kimi-K2.7-Code", "Kimi-K2.7-Code"),
            ModelPreset("Pro/moonshotai/Kimi-K2.6", "Pro Kimi-K2.6"),
            # MiniMax
            ModelPreset("MiniMaxAI/MiniMax-M2.5", "MiniMax-M2.5"),
            ModelPreset("Pro/MiniMaxAI/MiniMax-M2.5", "Pro MiniMax-M2.5"),
            # 其他厂商
            ModelPreset("nex-agi/Nex-N2-Pro", "Nex-N2-Pro"),
            ModelPreset("ByteDance-Seed/Seed-OSS-36B-Instruct", "Seed-OSS-36B-Instruct"),
            ModelPreset("stepfun-ai/Step-3.5-Flash", "Step-3.5-Flash"),
            ModelPreset("meituan-longcat/LongCat-2.0", "LongCat-2.0"),
            ModelPreset("tencent/Hunyuan-A13B-Instruct", "Hunyuan-A13B-Instruct"),
            ModelPreset("tencent/Hunyuan-MT-7B", "Hunyuan-MT-7B · 翻译"),
            ModelPreset("inclusionAI/Ling-flash-2.0", "Ling-flash-2.0"),
            ModelPreset("inclusionAI/Ling-mini-2.0", "Ling-mini-2.0"),
        ),
    ),
    ProviderPreset(
        id="openrouter",
        name="OpenRouter（多模型中转）",
        base_url="https://openrouter.ai/api/v1",
        key_tip="https://openrouter.ai/settings/keys",
        models=(
            ModelPreset("openai/gpt-5.6-sol", "OpenAI GPT-5.6 Sol"),
            ModelPreset("openai/gpt-5.6-terra", "OpenAI GPT-5.6 Terra"),
            ModelPreset("anthropic/claude-sonnet-5", "Anthropic Claude Sonnet 5"),
            ModelPreset("anthropic/claude-opus-5", "Anthropic Claude Opus 5"),
            ModelPreset("anthropic/claude-haiku-4-5", "Anthropic Claude Haiku 4.5"),
            ModelPreset("google/gemini-3.6-flash", "Google Gemini 3.6 Flash"),
            ModelPreset("google/gemini-3.1-pro-preview", "Google Gemini 3.1 Pro"),
            ModelPreset("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro"),
            ModelPreset("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash"),
            ModelPreset("qwen/qwen3.8-max", "Qwen3.8-Max"),
        ),
    ),
    ProviderPreset(
        id="anthropic",
        name="Anthropic Claude",
        base_url="https://api.anthropic.com",
        key_tip="https://console.anthropic.com",
        api_style=STYLE_ANTHROPIC,
        models=(
            ModelPreset("claude-sonnet-5", "Claude Sonnet 5 · 推荐"),
            ModelPreset("claude-opus-5", "Claude Opus 5 · 旗舰"),
            ModelPreset("claude-haiku-4-5", "Claude Haiku 4.5 · 轻量"),
            ModelPreset("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ModelPreset("claude-opus-4-6", "Claude Opus 4.6"),
        ),
    ),
    ProviderPreset(
        id="gemini",
        name="Google Gemini（OpenAI 兼容）",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        key_tip="https://aistudio.google.com/apikey",
        models=(
            ModelPreset("gemini-3.6-flash", "Gemini 3.6 Flash · 推荐"),
            ModelPreset("gemini-3.5-flash", "Gemini 3.5 Flash"),
            ModelPreset("gemini-3.1-pro-preview", "Gemini 3.1 Pro"),
            ModelPreset("gemini-3-flash-preview", "Gemini 3 Flash"),
            ModelPreset("gemini-2.5-flash", "Gemini 2.5 Flash · 兼容旧版"),
        ),
    ),
    ProviderPreset(
        id=CUSTOM_ID,
        name="自定义（任意 OpenAI 兼容接口）",
        base_url="",
        key_tip="",
        models=(),
    ),
]

PROVIDER_MAP: dict[str, ProviderPreset] = {p.id: p for p in PROVIDERS}

DEFAULT_BASE_URL = PROVIDER_MAP["deepseek"].base_url
DEFAULT_MODEL = PROVIDER_MAP["deepseek"].models[0].id
DEFAULT_TEMPERATURE = 0.8


def detect_provider(base_url: str) -> str | None:
    """根据 Base URL 反推服务商 id（旧配置迁移用）。"""
    if not base_url:
        return None
    url = base_url.rstrip("/").lower()
    for p in PROVIDERS:
        if p.id == CUSTOM_ID or not p.base_url:
            continue
        if url == p.base_url.rstrip("/").lower() or url.startswith(
            p.base_url.rstrip("/").lower()
        ):
            return p.id
    return None
