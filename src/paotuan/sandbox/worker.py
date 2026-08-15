"""沙箱子进程入口：读取 payload，在 RestrictedPython 白名单下执行 run()。"""

from __future__ import annotations

import argparse
import json
import sys


def build_safe_globals() -> dict:
    from RestrictedPython import safe_builtins
    from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
    from RestrictedPython.Guards import (
        full_write_guard,
        guarded_iter_unpack_sequence,
        guarded_unpack_sequence,
        safer_getattr_raise,
    )

    def guarded_inplacevar(op: str, x, *args):
        if op == "+=":
            return x + args[0]
        if op == "-=":
            return x - args[0]
        if op == "*=":
            return x * args[0]
        if op == "/=":
            return x / args[0]
        if op == "//=":
            return x // args[0]
        if op == "%=":
            return x % args[0]
        if op == "**=":
            return x ** args[0]
        raise NotImplementedError(f"不支持的就地运算: {op}")

    return {
        "__builtins__": safe_builtins,
        "_getattr_": safer_getattr_raise,
        "_getitem_": default_guarded_getitem,
        "_getiter_": default_guarded_getiter,
        "_write_": full_write_guard,
        "_unpack_sequence_": guarded_unpack_sequence,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_inplacevar_": guarded_inplacevar,
    }


def execute_script(code: str, state: dict, kwargs: dict) -> dict:
    from RestrictedPython import compile_restricted

    try:
        bytecode = compile_restricted(code, "<剧本脚本>", "exec")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"compile_error: {exc}", "error_type": "script"}

    namespace = build_safe_globals()
    try:
        exec(bytecode, namespace)
    except Exception as exc:  # noqa: BLE001
        # 受限环境运行失败（如 import、受禁名称）属于沙箱拒绝
        return {
            "ok": False,
            "error": f"exec_error: {type(exc).__name__}: {exc}",
            "error_type": "sandbox",
        }

    run = namespace.get("run")
    if not callable(run):
        return {
            "ok": False,
            "error": "脚本必须定义 run(state, **kwargs)",
            "error_type": "script",
        }

    try:
        result = run(state, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "error_type": "script",
        }

    if not isinstance(result, dict):
        return {
            "ok": False,
            "error": "run() 必须返回 dict",
            "error_type": "sandbox",
        }

    try:
        json.dumps(result)
    except (TypeError, ValueError) as exc:
        return {
            "ok": False,
            "error": f"状态不可 JSON 序列化: {exc}",
            "error_type": "sandbox",
        }

    return {"ok": True, "state": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    args = parser.parse_args()

    with open(args.payload, encoding="utf-8") as f:
        payload = json.load(f)

    code = open(payload["script"], encoding="utf-8").read()
    result = execute_script(
        code,
        payload.get("state", {}),
        payload.get("kwargs", {}),
    )
    with open(payload["out"], "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())