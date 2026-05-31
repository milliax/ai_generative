from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from shared.models import AgentMessage, OrderSpec, OrderRequest
from .base import BaseAgent

PROMPT = """
你是 Order Intake agent。將客戶的口語訂單解析成結構化的電纜規格。
輸出欄位：customer_name, product_family, product_description, core_count,
section_area_mm2, quantity_ton, priority, customer_type, promise_type,
requested_delivery (ISO date), urgency (normal|rush|emergency)
"""

SYSTEM_PROMPT = """你從客戶的自由文字中提取結構化的電纜訂單規格。"""


class OrderIntakeAgent(BaseAgent):
    name = "order_intake"
    system_prompt = SYSTEM_PROMPT

    def run(self, payload: dict[str, Any]) -> AgentMessage:
        req_data = payload.get("request")
        if isinstance(req_data, dict):
            raw = req_data.get("raw_text", "")
            received_at = req_data.get("received_at")
            urgency = req_data.get("urgency") or "normal"
        else:
            raw = ""
            received_at = None
            urgency = "normal"

        # W1 stub：簡單關鍵字判斷
        quantity_ton = 10.0
        if "50噸" in raw or "50 噸" in raw:
            quantity_ton = 50.0
        for token in raw.split():
            if token.replace(".", "").isdigit():
                quantity_ton = float(token)
                break

        urgency_detected = urgency
        if "急" in raw or "緊急" in raw or "ASAP" in raw:
            urgency_detected = "rush"

        requested_delivery = date.today() + timedelta(days=30)
        if "兩週" in raw or "14天" in raw:
            requested_delivery = date.today() + timedelta(days=14)
        if "一週" in raw or "7天" in raw:
            requested_delivery = date.today() + timedelta(days=7)

        spec = OrderSpec(
            customer_name=req_data.get("customer", "unknown") if isinstance(req_data, dict) else "unknown",
            product_family="低壓電力電纜",   # W1 預設，W2 換 LLM 解析
            product_description="XLPE 電力電纜",
            core_count="3C",
            section_area_mm2="240",
            quantity_ton=quantity_ton,
            priority="緊急" if urgency_detected != "normal" else "一般",
            customer_type="工程商",
            promise_type="硬交期" if urgency_detected != "normal" else "軟交期",
            requested_delivery=requested_delivery,
            urgency=urgency_detected,
            spec_diff={},
        )

        reasoning = (
            f"Stub intake: 從口語文字提取數量 {quantity_ton} 噸，"
            f"urgency={urgency_detected}，其餘欄位使用預設值。W2 換 LLM 解析。"
        )

        return AgentMessage(
            from_agent=self.name,
            to_agent=None,
            payload=spec.model_dump(),
            reasoning=reasoning,
        )