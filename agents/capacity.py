from __future__ import annotations

from typing import Any

from shared.models import AgentMessage
from .base import BaseAgent

PROMPT = """
你是 Capacity agent。根據電纜訂單的數量與產品族群，評估產線負載與換線風險。
輸出：capacity_status (OK|OVERLOAD), estimated_production_days, changeover_risk
"""

SYSTEM_PROMPT = """評估電纜廠產線產能，標記過載與換線風險。"""


class CapacityAgent(BaseAgent):
    name = "capacity"
    system_prompt = SYSTEM_PROMPT

    def run(self, payload: dict[str, Any]) -> AgentMessage:
        spec = payload.get("spec", {})
        quantity_ton = float(spec.get("quantity_ton", 1.0))
        product_family = spec.get("product_family", "")

        # W1 stub：簡單規則
        tons_per_day = 2.0
        estimated_days = round(quantity_ton / tons_per_day)
        status = "OVERLOAD" if quantity_ton > 100 else "OK"

        # 高壓電纜換線成本高
        if "高壓" in product_family:
            changeover_risk = "高：高壓電纜換線需清機，預估損耗 NTD 50,000"
        else:
            changeover_risk = "低：標準低壓電纜，換線成本可接受"

        reasoning = (
            f"Stub capacity: {quantity_ton} 噸 / {tons_per_day} 噸/天 "
            f"= 預估 {estimated_days} 天，狀態={status}，{changeover_risk}。"
        )

        return AgentMessage(
            from_agent=self.name,
            to_agent=None,
            payload={
                "capacity_status": status,
                "estimated_production_days": estimated_days,
                "changeover_risk": changeover_risk,
            },
            reasoning=reasoning,
        )