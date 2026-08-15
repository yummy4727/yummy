"""最终文本生成（含后处理审查，违规则重试，上限 3 次）。"""

from __future__ import annotations

import logging
from typing import Sequence

from paotuan.censor import SensitiveFilter
from paotuan.llm import LLMClient

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
FALLBACK_TEXT = "（生成内容未通过安全审查，已替换为兜底回复。）"


def generate_text_with_censor(
    llm: LLMClient,
    messages: Sequence[dict[str, str]],
    censor: SensitiveFilter,
    max_retries: int = MAX_RETRIES,
) -> str:
    for attempt in range(1, max_retries + 1):
        text = llm.generate_text(messages)
        if censor.check(text):
            logger.warning("输出未通过审查（第 %d 次）", attempt)
            continue
        return text
    logger.error("输出连续 %d 次未通过审查，使用兜底文本", max_retries)
    return FALLBACK_TEXT
