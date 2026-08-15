"""子进程执行器：超时 kill、结果回收、临时文件清理。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .limits import DEFAULT_TIMEOUT, MAX_OUTPUT_BYTES

_WORKER = Path(__file__).resolve().parent / "worker.py"


@dataclass
class ScriptResult:
    ok: bool
    state: dict | None = None
    error: str | None = None
    error_type: str = ""
    elapsed: float = 0.0


class SandboxRunner:
    """在独立子进程中执行剧本脚本，超时则由父进程 kill。

    不使用线程内超时——Python 线程不可强制终止，死循环脚本必须靠杀进程回收。
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout

    def execute(
        self,
        script_path: str | Path,
        state: dict,
        kwargs: dict | None = None,
    ) -> ScriptResult:
        script_path = Path(script_path)
        if not script_path.is_file():
            return ScriptResult(ok=False, error=f"脚本不存在: {script_path}")

        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="paotuan_sandbox_") as tmp:
            tmp_dir = Path(tmp)
            payload_file = tmp_dir / "payload.json"
            out_file = tmp_dir / "result.json"

            payload = {
                "script": str(script_path),
                "state": state,
                "kwargs": kwargs or {},
                "out": str(out_file),
            }
            payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            proc = subprocess.Popen(
                [sys.executable, str(_WORKER), "--payload", str(payload_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                stdout, stderr = proc.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return ScriptResult(
                    ok=False,
                    error=f"脚本执行超时（{self.timeout:g}s），已终止子进程",
                    error_type="timeout",
                    elapsed=time.monotonic() - start,
                )

            elapsed = time.monotonic() - start

            if proc.returncode != 0:
                return ScriptResult(
                    ok=False,
                    error=f"子进程异常退出（code={proc.returncode}）",
                    error_type="subprocess",
                    elapsed=elapsed,
                )

            if not out_file.is_file():
                return ScriptResult(
                    ok=False,
                    error="子进程未产出结果文件",
                    error_type="no_result",
                    elapsed=elapsed,
                )

            if out_file.stat().st_size > MAX_OUTPUT_BYTES:
                return ScriptResult(
                    ok=False,
                    error=f"脚本输出超过 {MAX_OUTPUT_BYTES} 字节上限",
                    error_type="output_too_large",
                    elapsed=elapsed,
                )

            try:
                result = json.loads(out_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return ScriptResult(
                    ok=False,
                    error="结果文件不是合法 JSON",
                    error_type="bad_result",
                    elapsed=elapsed,
                )

            if result.get("ok"):
                return ScriptResult(
                    ok=True,
                    state=result.get("state"),
                    elapsed=elapsed,
                )
            return ScriptResult(
                ok=False,
                error=result.get("error", "未知错误"),
                error_type=result.get("error_type", "script"),
                elapsed=elapsed,
            )
