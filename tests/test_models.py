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
        customer_name="台電",
        product_family="高壓電纜",
        product_description="15KV XLPE 電力電纜",
        core_count="3C",
        section_area_mm2="240",
        quantity_ton=15,
        priority="急單",
        customer_type="公營事業",
        promise_type="指定交期",
        requested_delivery=date(2026, 8, 1),
        spec_diff={"quantity_ton": {"from": 10, "to": 15}},
        urgency="rush",
    )
    assert spec.urgency == "rush"
    assert spec.spec_diff["quantity_ton"]["to"] == 15


def test_order_spec_rejects_bad_urgency():
    with pytest.raises(ValidationError):
        OrderSpec(
            customer_name="台電",
            product_family="高壓電纜",
            product_description="15KV XLPE 電力電纜",
            core_count="3C",
            section_area_mm2="240",
            quantity_ton=1,
            priority="一般",
            customer_type="公營事業",
            promise_type="指定交期",
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
        estimated_price_ntd=100000.0,
        price_confidence=(95000.0, 105000.0),
        estimated_delivery=date(2026, 8, 15),
        capacity_status="OK",
        changeover_risk="低：標準產品換線成本可接受",
        reference_orders=[{"order_id": "A001", "similarity": 0.92}],
        risks=["material shortage"],
        next_actions=["confirm with customer"],
    )
    assert plan.estimated_price_ntd == 100000.0
    assert len(plan.reference_orders) == 1


def test_order_spec_rejects_zero_memory():
    with pytest.raises(ValidationError):
        OrderSpec(
            customer_name="台電", product_family="高壓電纜",
            product_description="15KV XLPE 電力電纜", core_count="3C",
            section_area_mm2="240", quantity_ton=0,
            priority="一般", customer_type="公營事業", promise_type="指定交期",
            requested_delivery=date.today(),
            spec_diff={}, urgency="normal",
        )


def test_order_spec_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        OrderSpec(
            customer_name="台電", product_family="高壓電纜",
            product_description="15KV XLPE 電力電纜", core_count="3C",
            section_area_mm2="240", quantity_ton=0,
            priority="一般", customer_type="公營事業", promise_type="指定交期",
            requested_delivery=date.today(),
            spec_diff={}, urgency="normal",
        )


def test_order_spec_rejects_empty_cpu_sku():
    with pytest.raises(ValidationError):
        OrderSpec(
            customer_name="", product_family="高壓電纜",
            product_description="15KV XLPE 電力電纜", core_count="3C",
            section_area_mm2="240", quantity_ton=1,
            priority="一般", customer_type="公營事業", promise_type="指定交期",
            requested_delivery=date.today(),
            spec_diff={}, urgency="normal",
        )


def test_coordination_plan_rejects_inverted_confidence():
    from pydantic import ValidationError as VE
    with pytest.raises(VE):
        CoordinationPlan(
            estimated_price_ntd=100.0,
            price_confidence=(200.0, 100.0),  # inverted!
            estimated_delivery=date(2026, 8, 1),
            capacity_status="OK",
            changeover_risk="低",
            reference_orders=[],
            risks=[],
            next_actions=[],
        )


def test_coordination_plan_rejects_bad_capacity_status():
    with pytest.raises(ValidationError):
        CoordinationPlan(
            estimated_price_ntd=100.0,
            price_confidence=(90.0, 110.0),
            estimated_delivery=date(2026, 8, 1),
            capacity_status="MAYBE",  # not in Literal
            changeover_risk="低",
            reference_orders=[],
            risks=[],
            next_actions=[],
        )
