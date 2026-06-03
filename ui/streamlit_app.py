"""Streamlit panel: startup data-onboarding gate + main coordination panel.

Run: streamlit run ui/streamlit_app.py
UI rules: no litellm import, no business logic, no hardcoded .env, no schema changes.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# `streamlit run ui/streamlit_app.py` puts ui/ on sys.path, not the project root,
# so make the project root importable for the agents/ and shared/ packages.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from agents.orchestrator import retrieve_similar, run_orchestrator
from shared.data_pipeline import DEFAULT_RAW_DIR, data_status, run_full_pipeline
from shared.models import OrderRequest
from ui.order_detail import render_order_card

DEMO_SCENARIOS = {
    "（自訂）": "",
    "正常單": "AWS Q3 訂單：1000 噸 CV 250mm2 電纜，8 月底前交貨",
    "急單": "Meta 緊急加單：兩週內需要 500 噸 IV 100mm2，產線可能要外援",
    "規格變更": "原 Google 訂單規格變更：芯數從單芯改雙芯，數量不變，重新評估",
}

STEP_LABELS = {
    "build_db": "建立 SQLite 資料庫",
    "convert": "產生 RAG 訂單 CSV",
    "ingest": "建立向量索引",
}

st.set_page_config(page_title="綠色供應鏈協調系統", page_icon="🌱", layout="wide")


def render_gate(status) -> None:
    if status.raw_excel_path is None:
        st.warning("🗂️ 尚未載入資料")
        st.write(f"請將老師的 Excel 放到 `{DEFAULT_RAW_DIR}/` 後按下方按鈕。")
        if st.button("🔄 重新偵測"):
            st.rerun()
        return

    st.success(f"✅ 偵測到：{status.raw_excel_path.name}")
    st.caption("（預期 9 個工作表 · 約 3000 筆訂單）")
    if st.button("⚙️ 開始轉檔"):
        _run_conversion(status.raw_excel_path)


def _run_conversion(excel_path) -> None:
    with st.status("⚙️ 資料轉檔中…", expanded=True) as box:
        def on_progress(step: str, state: str, detail: str) -> None:
            label = STEP_LABELS.get(step, step)
            if state == "running":
                box.write(f"🔄 {label}…（{detail}）")
            elif state == "done":
                box.write(f"✅ {label}（{detail}）")

        try:
            run_full_pipeline(excel_path=excel_path, progress_callback=on_progress)
            box.update(label="✅ 轉檔完成", state="complete")
        except Exception as exc:  # noqa: BLE001 — show the failing step to the user
            box.update(label="❌ 轉檔失敗", state="error")
            st.error(f"轉檔失敗：{type(exc).__name__}: {exc}")
            if st.button("🔁 重試"):
                st.rerun()
            return
    st.balloons()
    if st.button("✅ 進入系統"):
        st.rerun()


def render_data_status_tab(status) -> None:
    st.subheader("資料狀態")
    c1, c2, c3 = st.columns(3)
    c1.metric("SQLite 表數", status.db_tables)
    c2.metric("RAG CSV 列數", status.csv_rows)
    c3.metric("向量索引筆數", status.chroma_count)
    if st.button("♻️ 重建資料"):
        st.session_state.pop("chat", None)
        st.session_state.pop("search_results", None)
        st.rerun()


def _render_plan(plan) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 預估單價", f"${plan.estimated_price_ntd:,.0f}/噸")
    low, high = plan.price_confidence
    c1.caption(f"信心區間 ${low:,.0f} ～ ${high:,.0f}")
    c2.metric("📅 預估交期", str(plan.estimated_delivery))
    c3.metric("🏭 產能", plan.capacity_status)
    if plan.changeover_risk:
        st.caption(f"換線風險：{plan.changeover_risk}")

    for risk in plan.risks:
        st.warning(risk)

    if plan.reference_orders:
        st.markdown("**📄 參考歷史訂單**")
        for i, ref in enumerate(plan.reference_orders):
            render_order_card(ref, key=f"chatref-{id(plan)}-{i}")

    if plan.next_actions:
        st.markdown("**下一步**")
        for action in plan.next_actions:
            st.write(f"- {action}")


def render_chat_tab() -> None:
    st.subheader("💬 協調聊天")
    chat = st.session_state.setdefault("chat", [])

    cols = st.columns(len(DEMO_SCENARIOS))
    for col, (name, text) in zip(cols, DEMO_SCENARIOS.items()):
        if text and col.button(name, key=f"demo-{name}"):
            st.session_state["prefill"] = text
    customer = st.text_input("客戶名稱（選填）")

    for msg in chat:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["text"])
            else:
                _render_plan(msg["plan"])

    prompt = st.chat_input("輸入客戶需求…") or st.session_state.pop("prefill", None)
    if not prompt:
        return

    chat.append({"role": "user", "text": prompt})
    order = OrderRequest(
        customer=customer or "未具名客戶",
        raw_text=prompt,
        received_at=datetime.now(),
        urgency=None,
    )
    try:
        with st.status("🤖 Agents 協調中…", expanded=False):
            plan = run_orchestrator(order)
    except Exception as exc:  # noqa: BLE001 — surface failure, keep conversation
        st.error(f"協調失敗：{type(exc).__name__}: {exc}")
        return
    chat.append({"role": "assistant", "plan": plan})
    st.rerun()


def render_search_tab() -> None:
    st.subheader("🔍 歷史訂單檢索")
    query = st.text_input("搜尋歷史訂單（規格 / 客戶 / 描述）")
    k = st.slider("回傳筆數", min_value=1, max_value=10, value=5)
    if st.button("搜尋", disabled=not query.strip()):
        try:
            with st.spinner("檢索中…"):
                st.session_state["search_results"] = retrieve_similar(query, k=k)
        except Exception as exc:  # noqa: BLE001
            st.error(f"檢索失敗（請先在「資料狀態」頁完成轉檔）：{type(exc).__name__}: {exc}")
            return

    results = st.session_state.get("search_results")
    if results is None:
        st.info("輸入關鍵字後點「搜尋」。")
    elif not results:
        st.caption("（查無相似訂單）")
    else:
        for i, record in enumerate(results):
            render_order_card(record, key=f"search-{i}")


def main() -> None:
    status = data_status()
    if not (status.db_ready and status.csv_ready and status.chroma_ready):
        render_gate(status)
        return

    st.title("🌱 多 Agent 綠色供應鏈協調系統")
    tab_status, tab_chat, tab_search = st.tabs(["🗂️ 資料狀態", "💬 協調聊天", "🔍 歷史訂單檢索"])
    with tab_status:
        render_data_status_tab(status)
    with tab_chat:
        render_chat_tab()
    with tab_search:
        render_search_tab()


main()
