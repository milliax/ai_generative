"""Streamlit panel: startup data-onboarding gate + main coordination panel.

Run: streamlit run ui/streamlit_app.py
UI rules: no litellm import, no business logic, no hardcoded .env, no schema changes.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from agents.orchestrator import run_orchestrator
from shared.data_pipeline import DEFAULT_RAW_DIR, data_status, run_full_pipeline
from shared.models import OrderRequest

URGENCY_OPTIONS = ["normal", "rush", "emergency"]  # Urgency = Literal[...] in shared/models

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


def render_sidebar(status) -> None:
    with st.sidebar:
        st.header("資料狀態")
        st.metric("SQLite 表數", status.db_tables)
        st.metric("RAG CSV 列數", status.csv_rows)
        st.metric("向量索引筆數", status.chroma_count)
        if st.button("♻️ 重建資料"):
            st.session_state.pop("plan", None)
            st.rerun()


def render_main_panel() -> None:
    st.title("🌱 多 Agent 綠色供應鏈協調系統")
    left, mid = st.columns([1, 2])

    with left:
        st.subheader("客戶需求輸入")
        scenario = st.selectbox("Demo 情境", list(DEMO_SCENARIOS.keys()))
        customer = st.text_input("客戶", value="AWS")
        raw_text = st.text_area("需求", value=DEMO_SCENARIOS[scenario], height=120)
        urgency = st.selectbox("急迫度", URGENCY_OPTIONS)
        if st.button("▶ 跑 Agent"):
            order = OrderRequest(
                customer=customer,
                raw_text=raw_text,
                received_at=datetime.now(),
                urgency=urgency,
            )
            with st.status("🤖 Agents 協調中…", expanded=False):
                st.session_state["plan"] = run_orchestrator(order)

    with mid:
        st.subheader("協調報告")
        plan = st.session_state.get("plan")
        if plan is None:
            st.info("輸入需求後點「▶ 跑 Agent」。")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 預估報價", f"${plan.estimated_price:,.0f}")
            c2.metric("📅 交期", str(plan.estimated_delivery))
            c3.metric("🌱 碳排", f"{plan.carbon_footprint_kg:,.0f} kg")
            st.caption("⚠️ W1 stub：報價／碳排為佔位值，待真實 agent 接上")
            st.markdown("**📊 參考歷史訂單**")
            if plan.reference_orders:
                st.dataframe(plan.reference_orders, use_container_width=True)
            else:
                st.caption("（無參考訂單）")
            if plan.risks:
                for risk in plan.risks:
                    st.warning(risk)
            if plan.next_actions:
                st.markdown("**下一步**")
                for action in plan.next_actions:
                    st.write(f"- {action}")


def main() -> None:
    status = data_status()
    if not (status.db_ready and status.csv_ready and status.chroma_ready):
        render_gate(status)
        return
    render_sidebar(status)
    render_main_panel()


main()
