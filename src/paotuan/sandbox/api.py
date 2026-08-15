"""沙箱对外统一接口。"""

from __future__ import annotations

from .runner import SandboxRunner, ScriptResult


def run_script(
    script_path: str | object,
    state: dict,
    kwargs: dict | None = None,
    timeout: float = 5.0,
) -> ScriptResult:
    """便捷入口：在子进程沙箱中执行剧本脚本。"""
    return SandboxRunner(timeout=timeout).execute(script_path, state, kwargs)


__all__ = ["SandboxRunner", "ScriptResult", "run_script"]