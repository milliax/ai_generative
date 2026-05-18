"""統一 LLM 呼叫介面。所有 agent 一律經過 call_llm()，不要直接 import litellm。"""
from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from litellm import completion

load_dotenv()

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """LLM 呼叫失敗（已用盡 retry）。"""


def call_llm(
    messages: list[dict],
    model: str | None = None,
    *,
    temperature: float = 0.2,
    max_retries: int = 3,
    **kwargs,
) -> str:
    """呼叫 LLM，回傳純文字。

    Args:
        messages: OpenAI-style 訊息列表 `[{"role": "user", "content": "..."}]`
        model: 覆寫環境變數 `LLM_MODEL`
        temperature: 預設 0.2（agent 任務需要穩定輸出）
        max_retries: 最多重試次數（指數退避）

    Raises:
        LLMError: 用盡 retry 仍失敗
    """
    model = model or os.getenv("LLM_MODEL", "gemini/gemini-1.5-flash")
    last_err: Exception | None = None

    for attempt in range(max_retries):
        try:
            resp = completion(
                model=model,
                messages=messages,
                temperature=temperature,
                **kwargs,
            )
            content = resp.choices[0].message.content
            logger.info("LLM call ok model=%s tokens≈%d", model, len(content))
            return content
        except Exception as e:
            last_err = e
            wait = 2**attempt
            logger.warning("LLM call failed (attempt %d): %s; retrying in %ds", attempt + 1, e, wait)
            time.sleep(wait)

    raise LLMError(f"LLM call failed after {max_retries} attempts: {last_err}")
