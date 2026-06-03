from ui.order_detail import group_order_fields


def test_groups_present_fields_with_labels():
    order = {
        "order_id": "A-001",
        "customer": "AWS",
        "quantity_ton": 1000.0,
        "product_family": "低壓電力電纜",
        "overall_risk_score": 0.42,
        "recommended_action": "標準排程",
        "similarity": 0.87,
    }

    grouped = group_order_fields(order)

    assert ("訂單編號", "A-001") in grouped["基本資訊"]
    assert ("客戶", "AWS") in grouped["基本資訊"]
    assert ("數量（噸）", 1000.0) in grouped["基本資訊"]
    assert ("產品族", "低壓電力電纜") in grouped["規格"]
    assert ("綜合風險", 0.42) in grouped["風險評分"]
    assert ("建議處置", "標準排程") in grouped["建議與摘要"]
    assert ("相似度", 0.87) in grouped["建議與摘要"]


def test_skips_missing_and_empty_fields():
    order = {
        "order_id": "A-002",
        "customer": "",          # empty string (sanitized NaN) -> skipped
        "recommended_action": None,  # None -> skipped
        # no spec / risk fields at all
    }

    grouped = group_order_fields(order)

    assert grouped["基本資訊"] == [("訂單編號", "A-002")]
    # groups with no present fields are omitted entirely
    assert "規格" not in grouped
    assert "風險評分" not in grouped
    assert "建議與摘要" not in grouped


def test_preserves_field_order_within_group():
    order = {"customer": "Meta", "order_id": "A-003"}

    grouped = group_order_fields(order)

    # order_id is declared before customer in the group spec
    assert grouped["基本資訊"] == [("訂單編號", "A-003"), ("客戶", "Meta")]
