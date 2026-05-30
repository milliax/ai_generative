from datetime import datetime

from shared.models import CoordinationPlan, OrderRequest
from agents import orchestrator


def _order() -> OrderRequest:
    return OrderRequest(
        customer="測試客戶",
        raw_text="需要 100 噸 CV 250mm2 電纜，兩週內交貨",
        received_at=datetime(2026, 5, 30, 10, 0, 0),
        urgency="rush",
    )


def test_run_orchestrator_returns_valid_plan(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "retrieve_similar",
        lambda query, k=3, **kw: [{"order_id": "O1", "similarity": 0.9, "matched_summary": "x"}],
    )
    plan = orchestrator.run_orchestrator(_order())
    assert isinstance(plan, CoordinationPlan)
    assert plan.reference_orders == [{"order_id": "O1", "similarity": 0.9, "matched_summary": "x"}]


def test_run_orchestrator_degrades_when_retrieval_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("chroma down")

    monkeypatch.setattr(orchestrator, "retrieve_similar", boom)
    plan = orchestrator.run_orchestrator(_order())
    assert isinstance(plan, CoordinationPlan)
    assert plan.reference_orders == []
    assert any("RAG" in r or "檢索" in r for r in plan.risks)
