from datetime import date, datetime
import pytest
from pydantic import ValidationError
from shared.models import (
    OrderRequest, OrderSpec, AgentMessage, CoordinationPlan,
)


def test_order_request_minimal():
    req = OrderRequest(
        customer="AWS",
        raw_text="Need 1000 servers Q3",
        received_at=datetime(2026, 5, 18, 10, 0),
    )
    assert req.urgency is None
    assert req.customer == "AWS"


def test_order_spec_full():
    spec = OrderSpec(
        cpu_sku="Xeon-9654",
        memory_gb=512,
        storage_tb=20,
        chassis="2U",
        quantity=1000,
        requested_delivery=date(2026, 8, 1),
        spec_diff={"memory_gb": {"from": 256, "to": 512}},
        urgency="rush",
    )
    assert spec.urgency == "rush"
    assert spec.spec_diff["memory_gb"]["to"] == 512


def test_order_spec_rejects_bad_urgency():
    with pytest.raises(ValidationError):
        OrderSpec(
            cpu_sku="X",
            memory_gb=1,
            storage_tb=1,
            chassis="1U",
            quantity=1,
            requested_delivery=date.today(),
            spec_diff={},
            urgency="super-urgent",  # not in Literal
        )


def test_agent_message_roundtrip():
    msg = AgentMessage(
        from_agent="pricing",
        to_agent=None,
        payload={"price": 1234.5},
        reasoning="similar to order #42",
    )
    assert msg.to_agent is None
    assert msg.payload["price"] == 1234.5


def test_coordination_plan_minimal():
    plan = CoordinationPlan(
        estimated_price=100000.0,
        price_confidence=(95000.0, 105000.0),
        estimated_delivery=date(2026, 8, 15),
        carbon_footprint_kg=1234.5,
        capacity_status="OK",
        alternative_suppliers=[],
        reference_orders=[{"order_id": "A001", "similarity": 0.92}],
        risks=["material shortage"],
        next_actions=["confirm with customer"],
    )
    assert plan.estimated_price == 100000.0
    assert len(plan.reference_orders) == 1


def test_order_spec_rejects_zero_memory():
    with pytest.raises(ValidationError):
        OrderSpec(
            cpu_sku="X", memory_gb=0, storage_tb=1, chassis="1U",
            quantity=1, requested_delivery=date.today(),
            spec_diff={}, urgency="normal",
        )


def test_order_spec_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        OrderSpec(
            cpu_sku="X", memory_gb=1, storage_tb=1, chassis="1U",
            quantity=0, requested_delivery=date.today(),
            spec_diff={}, urgency="normal",
        )


def test_order_spec_rejects_empty_cpu_sku():
    with pytest.raises(ValidationError):
        OrderSpec(
            cpu_sku="", memory_gb=1, storage_tb=1, chassis="1U",
            quantity=1, requested_delivery=date.today(),
            spec_diff={}, urgency="normal",
        )


def test_coordination_plan_rejects_inverted_confidence():
    from pydantic import ValidationError as VE
    with pytest.raises(VE):
        CoordinationPlan(
            estimated_price=100.0,
            price_confidence=(200.0, 100.0),  # inverted!
            estimated_delivery=date(2026, 8, 1),
            carbon_footprint_kg=10.0,
            capacity_status="OK",
            alternative_suppliers=[],
            reference_orders=[],
            risks=[],
            next_actions=[],
        )


def test_coordination_plan_rejects_bad_capacity_status():
    with pytest.raises(ValidationError):
        CoordinationPlan(
            estimated_price=100.0,
            price_confidence=(90.0, 110.0),
            estimated_delivery=date(2026, 8, 1),
            carbon_footprint_kg=10.0,
            capacity_status="MAYBE",  # not in Literal
            alternative_suppliers=[],
            reference_orders=[],
            risks=[],
            next_actions=[],
        )
