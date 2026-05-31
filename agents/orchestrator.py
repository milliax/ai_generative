from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, TypedDict

from shared.models import AgentMessage, CoordinationPlan, OrderRequest, OrderSpec
from agents.order_intake import OrderIntakeAgent
from agents.capacity import CapacityAgent
from agents.esg import ESGAgent
from agents.pricing import PricingAgent


def retrieve_similar(query: str, k: int = 3, **kwargs: Any) -> list[dict[str, Any]]:
    """Lazy-load retrieval helper so orchestrator imports even without ChromaDB installed."""
    try:
        from pricing.retrieval import retrieve_similar as _retrieve_similar
    except ImportError as exc:
        raise RuntimeError(
            "RAG retrieval dependency is not installed. "
            "Install chromadb and sentence-transformers or disable RAG retrieval."
        ) from exc

    return _retrieve_similar(query=query, k=k, **kwargs)


class OrchestratorState(TypedDict):
    request: OrderRequest
    spec: dict[str, Any]
    capacity_result: dict[str, Any]
    pricing_result: dict[str, Any]
    esg_result: dict[str, Any]
    trace: list[AgentMessage]


def _run_capacity(spec: dict[str, Any]) -> AgentMessage:
    """Stub capacity check: estimate hours and flag overload."""
    quantity = int(spec.get("quantity", 1))
    chassis = spec.get("chassis", "4U")
    hours_per_chassis = 10 if "U" in chassis else 8
    used_hours = quantity * hours_per_chassis
    status = "OVERLOAD" if used_hours > 5000 else "OK"

    reasoning = (
        "Stub capacity: estimated required production hours from quantity and chassis type. "
        f"Calculated {used_hours} hours and marked status {status}."
    )

    return AgentMessage(
        from_agent="capacity",
        to_agent=None,
        payload={
            "used_hours": used_hours,
            "hours_per_chassis": hours_per_chassis,
            "capacity_status": status,
        },
        reasoning=reasoning,
    )


def _run_esg(spec: dict[str, Any]) -> AgentMessage:
    """Stub ESG: estimate carbon footprint and suggest alternative suppliers."""
    quantity = int(spec.get("quantity", 1))
    kg_per_chassis = 25.0
    carbon_footprint = round(quantity * kg_per_chassis, 2)

    suppliers = [
        {
            "supplier_id": "S-Alpha",
            "reason": "Lower-carbon copper sourcing",
            "estimated_lead_days": 35,
        },
        {
            "supplier_id": "S-Beta",
            "reason": "Recycled insulation materials",
            "estimated_lead_days": 40,
        },
    ]

    reasoning = (
        "Stub ESG review: used fixed carbon factor per chassis and returned two alternative suppliers "
        "with greener materials."
    )

    return AgentMessage(
        from_agent="esg",
        to_agent=None,
        payload={
            "carbon_footprint_kg": carbon_footprint,
            "alternative_suppliers": suppliers,
        },
        reasoning=reasoning,
    )


def _aggregate(state: OrchestratorState, reference_orders: list[dict[str, Any]]) -> CoordinationPlan:
    pricing_payload = state["pricing_result"]["payload"]
    #esg_payload = state["esg_result"]["payload"]
    capacity_payload = state["capacity_result"]["payload"]

    estimated_delivery = pricing_payload.get("estimated_delivery")
    if isinstance(estimated_delivery, str):
        estimated_delivery = date.fromisoformat(estimated_delivery)
    elif isinstance(estimated_delivery, datetime):
        estimated_delivery = estimated_delivery.date()
    elif isinstance(estimated_delivery, date):
        estimated_delivery = estimated_delivery
    else:
        estimated_delivery = date.today() + timedelta(days=30)

    risks: list[str] = []
    if capacity_payload.get("capacity_status") == "OVERLOAD":
        risks.append("Capacity is overloaded — investigate additional production partners.")

    return CoordinationPlan(
        estimated_price_ntd=float(pricing_payload.get("estimated_price", 0.0)),
        price_confidence=tuple(pricing_payload.get("price_confidence", [0.0, 0.0])),
        estimated_delivery=estimated_delivery,
        capacity_status=capacity_payload.get("capacity_status", "OK"),
        changeover_risk=str(capacity_payload.get("changeover_risk", "")),
        #carbon_footprint_kg=float(esg_payload.get("carbon_footprint_kg", 0.0)),
        #alternative_suppliers=esg_payload.get("alternative_suppliers", []),
        reference_orders=reference_orders,
        risks=risks,
        next_actions=[
            "Verify copper material availability with procurement.",
            "Assess production scheduling feasibility with manufacturing planning.",
            "Prepare a customer response covering quotation and lead time.",
        ],
    )


def run_orchestrator(request: OrderRequest) -> CoordinationPlan:
    """Run the agent pipeline from intake through aggregation."""
    state: OrchestratorState = {
        "request": request,
        "spec": {},
        "capacity_result": {},
        "pricing_result": {},
        "esg_result": {},
        "trace": [],
    }

    # Step 1: Order Intake — 解析口語訂單成結構化規格
    intake_agent = OrderIntakeAgent()
    intake_msg = intake_agent.run({"request": request.model_dump()})
    state["spec"] = intake_msg.payload
    state["trace"].append(intake_msg)

    # Step 2: Capacity — 產線負載評估
    capacity_agent = CapacityAgent()
    capacity_msg = capacity_agent.run({"spec": state["spec"]})
    state["capacity_result"] = capacity_msg.model_dump()
    state["trace"].append(capacity_msg)

    # Step 3: RAG 查詢 — 在 Pricing 之前執行，結果傳給 PricingAgent
    rag_records: list[dict[str, Any]] = []
    try:
        rag_records = retrieve_similar(request.raw_text, k=3)
    except Exception as exc:
        state["trace"].append(
            AgentMessage(
                from_agent="orchestrator",
                to_agent=None,
                payload={"error": str(exc)},
                reasoning="RAG retrieval failed; pricing will use fallback stub formula.",
            )
        )

    # Step 4: Pricing — 把 spec + rag_records 一起傳進去
    pricing_agent = PricingAgent()
    pricing_msg = pricing_agent.run({
        "spec": state["spec"],
        "rag_records": rag_records,
    })
    state["pricing_result"] = pricing_msg.model_dump()
    state["trace"].append(pricing_msg)

    # Step 5: ESG — W1 暫回空值
    esg_agent = ESGAgent()
    esg_msg = esg_agent.run({"spec": state["spec"]})
    state["esg_result"] = esg_msg.model_dump()
    state["trace"].append(esg_msg)

    # Step 6: 整合輸出
    reference_orders = state["pricing_result"]["payload"].get("reference_orders", [])
    plan = _aggregate(state, reference_orders)

    if not rag_records:
        plan.risks.append("RAG 檢索無結果，估價使用 stub 公式，建議人工複核。")

    return plan