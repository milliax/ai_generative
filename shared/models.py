"""Shared Pydantic schemas. ALL inter-agent messages MUST be validated through these."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Urgency = Literal["normal", "rush", "emergency"]


class OrderRequest(BaseModel):
    """客戶原始進單 — Orchestrator 的輸入。"""

    customer: str
    raw_text: str
    received_at: datetime
    urgency: Urgency | None = None


class OrderSpec(BaseModel):
    """Order Intake agent 解析後的結構化規格。"""

    cpu_sku: str = Field(min_length=1)
    memory_gb: int = Field(gt=0)
    storage_tb: int = Field(ge=0)
    chassis: str
    quantity: int = Field(gt=0)
    requested_delivery: date
    spec_diff: dict[str, Any] = Field(default_factory=dict)
    urgency: Urgency


class AgentMessage(BaseModel):
    """Agent 之間溝通的訊息。`to_agent=None` 表示送回 orchestrator。"""

    from_agent: str
    to_agent: str | None = None
    payload: dict[str, Any]
    reasoning: str = Field(min_length=1)


class CoordinationPlan(BaseModel):
    """系統最終輸出給業務的協調報告。"""

    estimated_price: float
    price_confidence: tuple[float, float]
    estimated_delivery: date
    carbon_footprint_kg: float
    capacity_status: str
    alternative_suppliers: list[dict[str, Any]]
    reference_orders: list[dict[str, Any]]
    risks: list[str]
    next_actions: list[str]

    @model_validator(mode="after")
    def _check_price_confidence_order(self) -> "CoordinationPlan":
        low, high = self.price_confidence
        if low > high:
            raise ValueError(f"price_confidence must be (low, high) — got ({low}, {high})")
        return self
