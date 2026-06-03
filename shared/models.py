"""Shared Pydantic schemas. ALL inter-agent messages MUST be validated through these."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Urgency = Literal["normal", "rush", "emergency"]
CapacityStatus = Literal["OK", "OVERLOAD"]


class OrderRequest(BaseModel):
    """客戶原始進單 — Orchestrator 的輸入。"""
    customer: str
    raw_text: str
    received_at: datetime
    urgency: Urgency | None = None


class OrderSpec(BaseModel):
    """Order Intake agent 解析後的結構化規格（電纜廠版本）。"""
    customer_name: str = Field(min_length=1)
    product_family: str = Field(description="產品族群，例如 低壓電力電纜、高壓電力電纜")
    product_description: str = Field(description="產品說明，例如 15KV XLPE 電力電纜")
    core_count: str = Field(description="芯數，例如 3C、1C")
    section_area_mm2: str = Field(description="截面積，例如 240，單位平方毫米")
    quantity_ton: float = Field(gt=0, description="需求數量（噸）")
    priority: str = Field(description="優先等級，例如 緊急、一般")
    customer_type: str = Field(description="客戶類型，例如 工程商、製造業")
    promise_type: str = Field(description="承諾類型，例如 硬交期、軟交期")
    requested_delivery: date
    urgency: Urgency
    spec_diff: dict[str, Any] = Field(default_factory=dict)


class AgentMessage(BaseModel):
    """Agent 之間溝通的訊息。`to_agent=None` 表示送回 orchestrator。"""
    from_agent: str
    to_agent: str | None = None
    payload: dict[str, Any]
    reasoning: str = Field(min_length=1)


class CoordinationPlan(BaseModel):
    """系統最終輸出給業務的協調報告。"""
    estimated_price_ntd: float = Field(description="建議單價（NTD/噸）")
    price_confidence: tuple[float, float]
    estimated_delivery: date
    capacity_status: CapacityStatus
    changeover_risk: str = Field(description="換線風險說明")
    reference_orders: list[dict[str, Any]]
    risks: list[str]
    next_actions: list[str]
    llm_analysis: str | None = Field(default=None, description="LLM 的條列式中文估價分析（若有）")

    @model_validator(mode="after")
    def _check_price_confidence_order(self) -> "CoordinationPlan":
        low, high = self.price_confidence
        if low > high:
            raise ValueError(f"price_confidence must be (low, high) — got ({low}, {high})")
        return self