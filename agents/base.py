from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from shared.models import AgentMessage


class BaseAgent(ABC):
    """Abstract base for specialist agents.

    Conventions (W1 stub):
    - `name` and `system_prompt` provided on subclasses
    - `call_llm_text()` uses `shared.llm_client.call_llm`
    - `run(payload)` returns an `AgentMessage`
    """

    name: str = ""
    system_prompt: str = ""

    def call_llm_text(self, user_prompt: str, **kwargs: Any) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            from shared.llm_client import call_llm
        except Exception as exc:
            raise RuntimeError(
                "LLM client not available; ensure dependencies are installed before calling LLM."
            ) from exc

        return call_llm(messages, **kwargs)

    @abstractmethod
    def run(self, payload: dict[str, Any]) -> AgentMessage:
        raise NotImplementedError
