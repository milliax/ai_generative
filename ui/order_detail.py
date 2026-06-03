"""Shared historical-order display: detail dialog + clickable card.

Used by both the coordination chat tab and the historical-order search tab.
A historical order is a plain dict (a RAG retrieval record or a CoordinationPlan
reference_orders entry), which already carries the full set of order columns.

UI rules: no business logic, no schema changes — only render given dicts.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# (group label, [(order key, field label), ...]) — order within each group is preserved.
FIELD_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("基本資訊", [
        ("order_id", "訂單編號"),
        ("customer", "客戶"),
        ("order_date", "下單日"),
        ("due_date", "交期"),
        ("quantity_ton", "數量（噸）"),
        ("copper_kg", "銅重（kg）"),
    ]),
    ("規格", [
        ("product_description", "產品說明"),
        ("product_family", "產品族"),
        ("core_count", "芯數"),
        ("section_area_mm2", "截面積（mm²）"),
        ("promise_type", "交期類型"),
        ("customer_type", "客戶類型"),
    ]),
    ("風險評分", [
        ("overall_risk_score", "綜合風險"),
        ("capacity_risk_score", "產能風險"),
        ("changeover_risk_score", "換線風險"),
        ("due_pressure_score", "交期壓力"),
        ("estimated_delay_days", "預估延誤（天）"),
        ("is_high_risk", "高風險"),
    ]),
    ("建議與摘要", [
        ("recommended_action", "建議處置"),
        ("matched_summary", "摘要"),
        ("spec_summary", "摘要"),
        ("similarity", "相似度"),
    ]),
]


def group_order_fields(order: dict[str, Any]) -> dict[str, list[tuple[str, Any]]]:
    """Group an order dict into labelled sections, skipping missing/empty fields.

    ChromaDB sanitizes missing values to "", so both None and "" are treated as absent.
    Groups with no present fields are omitted entirely.
    """
    grouped: dict[str, list[tuple[str, Any]]] = {}
    for group_label, fields in FIELD_GROUPS:
        rows: list[tuple[str, Any]] = []
        for key, label in fields:
            if key not in order:
                continue
            value = order[key]
            if value is None or value == "":
                continue
            rows.append((label, value))
        if rows:
            grouped[group_label] = rows
    return grouped


def render_order_detail(order: dict[str, Any]) -> None:
    """Render an order's full detail, grouped into sections."""
    grouped = group_order_fields(order)
    if not grouped:
        st.caption("（此筆訂單沒有可顯示的欄位）")
        return

    for group_label, rows in grouped.items():
        st.markdown(f"**{group_label}**")
        for label, value in rows:
            cols = st.columns([1, 2])
            cols[0].markdown(f"`{label}`")
            cols[1].write(value)


@st.dialog("訂單詳情")
def order_detail_dialog(order: dict[str, Any]) -> None:
    render_order_detail(order)


def render_order_card(order: dict[str, Any], key: str) -> None:
    """Render a one-line order summary with a button that opens the detail dialog."""
    order_id = order.get("order_id", "N/A")
    similarity = order.get("similarity")
    customer = order.get("customer", "")
    product = order.get("product_description", order.get("product_family", ""))

    label = f"📄 訂單 {order_id}"
    if similarity not in (None, ""):
        label += f"（相似度 {float(similarity):.2f}）"

    summary = " · ".join(p for p in (str(customer), str(product)) if p)
    if summary:
        st.caption(summary)
    if st.button(label, key=key):
        order_detail_dialog(order)
