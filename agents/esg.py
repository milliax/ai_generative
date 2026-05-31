from __future__ import annotations

from typing import Any

from shared.models import AgentMessage
from .base import BaseAgent

PROMPT = """
（預留）ESG agent：評估電纜原料碳足跡與 RoHS/REACH 合規性。
W1 暫不實作，回傳空佔位結果。
"""

SYSTEM_PROMPT = """ESG 合規評估（W1 stub，暫不實作）。"""


class ESGAgent(BaseAgent):
    name = "esg"
    system_prompt = SYSTEM_PROMPT

    def run(self, payload: dict[str, Any]) -> AgentMessage:
        return AgentMessage(
            from_agent=self.name,
            to_agent=None,
            payload={
                "carbon_footprint_kg": 0.0,
                "alternative_suppliers": [],
            },
            reasoning="W1 stub: ESG agent 暫不實作，回傳空佔位值。W2 補上碳足跡與合規查核。",
        )