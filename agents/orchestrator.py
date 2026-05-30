"""W1 STUB orchestrator — replace with the real LangGraph version in Agent Task 6.

Interface matches the real one: run_orchestrator(OrderRequest) -> CoordinationPlan.
Pricing reference orders come from the REAL pricing RAG; everything else is canned.
"""

from __future__ import annotations

from datetime import date

from pricing.retrieval import retrieve_similar
from shared.models import CoordinationPlan, OrderRequest


def _build_query(order: OrderRequest) -> str:
    """Build a retrieval query from the order text (approximates spec_summary)."""
    parts = [order.customer, order.raw_text]
    if order.urgency is not None:
        parts.append(order.urgency)  # Urgency is a Literal[str]
    return " ".join(p for p in parts if p)


def run_orchestrator(order: OrderRequest) -> CoordinationPlan:
    """Return a coordination plan. Pricing RAG is real; other fields are stubbed."""
    risks: list[str] = []
    try:
        reference_orders = retrieve_similar(_build_query(order), k=3)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully for the demo
        reference_orders = []
        risks.append(f"RAG 檢索暫時無法使用（{type(exc).__name__}），參考歷史訂單從缺")

    return CoordinationPlan(
        estimated_price=0.0,  # W1 stub
        price_confidence=(0.0, 0.0),  # W1 stub
        estimated_delivery=date(2026, 8, 15),  # W1 stub
        carbon_footprint_kg=0.0,  # W1 stub
        capacity_status="OK",  # W1 stub (CapacityStatus = Literal["OK","OVERLOAD"])
        alternative_suppliers=[],  # W1 stub
        reference_orders=reference_orders,
        risks=risks,
        next_actions=["W1 stub：等 Agent 組 Task 6 接真實 orchestrator"],
    )
