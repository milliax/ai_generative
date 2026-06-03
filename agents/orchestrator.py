from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, TypedDict

from agents.capacity import CapacityAgent
from agents.esg import ESGAgent
from agents.order_intake import OrderIntakeAgent
from agents.pricing import PricingAgent
from shared.models import AgentMessage, CoordinationPlan, OrderRequest, OrderSpec


def retrieve_similar(query: str, k: int = 3, **kwargs: Any) -> list[dict[str, Any]]:
    """Lazy-load retrieval so orchestrator can still import without RAG deps."""
    try:
        from pricing.retrieval import retrieve_similar as _retrieve_similar
    except ImportError as exc:
        raise RuntimeError(
            "RAG retrieval dependency is not installed. "
            "Install chromadb and sentence-transformers or disable RAG retrieval."
        ) from exc

    return _retrieve_similar(query=query, k=k, **kwargs)


def _build_query(order: OrderRequest) -> str:
    """Build a retrieval query from the order text, approximating spec_summary."""
    parts = [order.customer, order.raw_text]
    if order.urgency is not None:
        parts.append(order.urgency)
    return " ".join(p for p in parts if p)


def _build_query_from_spec(spec: dict[str, Any]) -> str:
    """Build a retrieval query from a structured spec, matching spec_summary fields."""
    parts = [
        spec.get("product_family"),
        spec.get("product_description"),
        spec.get("core_count"),
        str(spec.get("section_area_mm2", "")),
        spec.get("customer_name"),
    ]
    return " ".join(str(p) for p in parts if p)


class OrchestratorState(TypedDict):
    request: OrderRequest
    spec: dict[str, Any]
    capacity_result: dict[str, Any]
    pricing_result: dict[str, Any]
    esg_result: dict[str, Any]
    trace: list[AgentMessage]


def _aggregate(state: OrchestratorState, reference_orders: list[dict[str, Any]]) -> CoordinationPlan:
    pricing_payload = state["pricing_result"]["payload"]
    capacity_payload = state["capacity_result"]["payload"]

    estimated_delivery = pricing_payload.get("estimated_delivery")
    if isinstance(estimated_delivery, str):
        estimated_delivery = date.fromisoformat(estimated_delivery)
    elif isinstance(estimated_delivery, datetime):
        estimated_delivery = estimated_delivery.date()
    elif not isinstance(estimated_delivery, date):
        estimated_delivery = date.today() + timedelta(days=30)

    risks: list[str] = []
    if capacity_payload.get("capacity_status") == "OVERLOAD":
        risks.append("產能已過載，建議評估外援產線或調整交期。")

    warning = pricing_payload.get("warning")
    if warning:
        risks.append(str(warning))

    return CoordinationPlan(
        estimated_price_ntd=float(pricing_payload.get("estimated_price", 0.0)),
        price_confidence=tuple(pricing_payload.get("price_confidence", [0.0, 0.0])),
        estimated_delivery=estimated_delivery,
        capacity_status=capacity_payload.get("capacity_status", "OK"),
        changeover_risk=str(capacity_payload.get("changeover_risk", "")),
        reference_orders=reference_orders,
        risks=risks,
        next_actions=[
            "向採購確認銅料供應狀況。",
            "與生產排程確認產線可行性。",
            "準備給客戶的回覆，涵蓋報價與交期。",
        ],
        llm_analysis=pricing_payload.get("llm_analysis"),
    )


def run_orchestrator(
    request: OrderRequest | None = None,
    *,
    spec: OrderSpec | None = None,
) -> CoordinationPlan:
    """Run the agent pipeline from intake through aggregation.

    Pass `spec` to feed a fully-structured order (e.g. from the UI form) and skip
    the W1 intake stub. Pass `request` to parse free text via OrderIntakeAgent.
    """
    if spec is None and request is None:
        raise ValueError("run_orchestrator needs either request or spec.")

    state: OrchestratorState = {
        "request": request,
        "spec": {},
        "capacity_result": {},
        "pricing_result": {},
        "esg_result": {},
        "trace": [],
    }

    if spec is not None:
        state["spec"] = spec.model_dump()
        query = _build_query_from_spec(state["spec"])
    else:
        intake_msg = OrderIntakeAgent().run({"request": request.model_dump()})
        state["spec"] = intake_msg.payload
        state["trace"].append(intake_msg)
        query = _build_query(request)

    capacity_msg = CapacityAgent().run({"spec": state["spec"]})
    state["capacity_result"] = capacity_msg.model_dump()
    state["trace"].append(capacity_msg)

    rag_records: list[dict[str, Any]] = []
    try:
        rag_records = retrieve_similar(query, k=3)
    except Exception as exc:  # noqa: BLE001
        state["trace"].append(
            AgentMessage(
                from_agent="orchestrator",
                to_agent=None,
                payload={"error": str(exc)},
                reasoning="RAG retrieval failed; pricing will use fallback formula.",
            )
        )

    pricing_msg = PricingAgent().run(
        {
            "spec": state["spec"],
            "rag_records": rag_records,
        }
    )
    state["pricing_result"] = pricing_msg.model_dump()
    state["trace"].append(pricing_msg)

    esg_msg = ESGAgent().run({"spec": state["spec"]})
    state["esg_result"] = esg_msg.model_dump()
    state["trace"].append(esg_msg)

    reference_orders = state["pricing_result"]["payload"].get("reference_orders", [])
    return _aggregate(state, reference_orders)
