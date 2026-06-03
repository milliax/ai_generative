"""最小 smoke test：驗證整條 W1 流程能跑通不 crash。"""
from datetime import datetime
from shared.models import OrderRequest
from agents.orchestrator import run_orchestrator

def test_normal_order():
    request = OrderRequest(
        customer="台電工程處",
        raw_text="需要 15 噸低壓電力電纜，3C 240平方毫米，六週後交貨。",
        received_at=datetime.now(),
        urgency="normal",
    )
    plan = run_orchestrator(request)
    print("✅ 正常單")
    print(f"   估價：NTD {plan.estimated_price_ntd:,.0f}")
    print(f"   交期：{plan.estimated_delivery}")
    print(f"   產能：{plan.capacity_status}")
    print(f"   換線風險：{plan.changeover_risk}")
    print(f"   參考訂單：{len(plan.reference_orders)} 筆")
    print(f"   風險提示：{plan.risks}")

def test_urgent_order():
    request = OrderRequest(
        customer="宏遠營造",
        raw_text="緊急！需要 50 噸高壓電力電纜，1C 95平方毫米，一週內要到工地。",
        received_at=datetime.now(),
        urgency="rush",
    )
    plan = run_orchestrator(request)
    print("✅ 急單")
    print(f"   估價：NTD {plan.estimated_price_ntd:,.0f}")
    print(f"   產能：{plan.capacity_status}")
    print(f"   換線風險：{plan.changeover_risk}")

def test_overload_order():
    request = OrderRequest(
        customer="中華電信",
        raw_text="需要 200 噸低壓電力電纜，3C 150平方毫米，兩個月後交貨。",
        received_at=datetime.now(),
        urgency="normal",
    )
    plan = run_orchestrator(request)
    print("✅ 過載單")
    print(f"   產能：{plan.capacity_status}（應為 OVERLOAD）")
    print(f"   風險：{plan.risks}")

if __name__ == "__main__":
    test_normal_order()
    print()
    test_urgent_order()
    print()
    test_overload_order()