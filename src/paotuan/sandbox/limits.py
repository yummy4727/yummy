"""沙箱资源限制阈值。"""

from __future__ import annotations

# 脚本执行超时（秒）
DEFAULT_TIMEOUT = 5.0

# 结果（game_state 序列化后）体积上限
MAX_OUTPUT_BYTES = 10 * 1024 * 1024

# 单次脚本调用最多允许 20 次（防止脚本调用自身等）
MAX_CALLS_PER_TURN = 20
