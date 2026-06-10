"""Streamlit panel: startup data-onboarding gate + main coordination panel.

Run: streamlit run ui/streamlit_app.py
UI rules: no litellm import, no business logic, no hardcoded .env, no schema changes.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# `streamlit run ui/streamlit_app.py` puts ui/ on sys.path, not the project root,
# so make the project root importable for the agents/ and shared/ packages.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from agents.orchestrator import run_orchestrator
from shared.data_pipeline import DEFAULT_CSV_PATH, DEFAULT_RAW_DIR, data_status, run_full_pipeline
from shared.models import OrderSpec
from ui.order_detail import order_detail_dialog, render_order_card

HISTORY_COLUMNS = [
    "order_id", "customer", "order_date", "due_date", "product_family",
    "product_description", "quantity_ton", "overall_risk_score",
    "is_high_risk", "estimated_delay_days", "recommended_action",
]

STEP_LABELS = {
    "build_db": "建立 SQLite 資料庫",
    "convert": "產生 RAG 訂單 CSV",
    "ingest": "建立向量索引",
}

st.set_page_config(page_title="綠色供應鏈協調系統", page_icon="🌱", layout="wide")

# 把系統標題放進頂部 header bar（與 Deploy 同高），省掉大標題佔的垂直空間。
# 非官方 API：依賴 stHeader 的 data-testid，換 Streamlit 版本時可能要再調。
st.markdown(
    """
    <style>
    [data-testid="stHeader"]::before {
        content: "🌱 多 Agent 綠色供應鏈協調系統";
        position: absolute;
        left: 16.5rem;  /* sidebar 展開時：標題讓到側欄右邊 */
        top: 50%;
        transform: translateY(-50%);
        font-size: 1.05rem;
        font-weight: 600;
        white-space: nowrap;
        transition: left 200ms ease;
    }
    /* sidebar 收合時：標題靠左（留出展開鈕的位置）*/
    .stApp:has(section[data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stHeader"]::before {
        left: 3.5rem;
    }

    /* shadcn 風格側欄導覽：把 st.radio 的圓圈藏起來，整列做成可點的 nav item */
    section[data-testid="stSidebar"] div[role="radiogroup"] {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        width: 100%;
        margin: 0;
        padding: 0.5rem 0.75rem;
        border-radius: 0.5rem;
        cursor: pointer;
        transition: background 120ms ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
        display: none;  /* 隱藏 radio 圓圈 */
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(128, 128, 128, 0.12);
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(128, 128, 128, 0.20);
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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
        st.session_state.pop("results", None)
        _load_orders.clear()
        st.rerun()


def _render_plan(plan, key_prefix: str) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 預估單價", f"${plan.estimated_price_ntd:,.0f}/噸")
    low, high = plan.price_confidence
    c1.caption(f"信心區間 ${low:,.0f} ～ ${high:,.0f}")
    c2.metric("📅 預估交期", str(plan.estimated_delivery))
    c3.metric("🏭 產能", plan.capacity_status)
    if plan.changeover_risk:
        st.caption(f"換線風險：{plan.changeover_risk}")

    if plan.llm_analysis:
        st.markdown("**🧠 AI 估價分析**")
        st.markdown(plan.llm_analysis)

    for risk in plan.risks:
        st.warning(risk)

    if plan.reference_orders:
        st.markdown("**📄 參考歷史訂單**")
        for i, ref in enumerate(plan.reference_orders):
            render_order_card(ref, key=f"{key_prefix}-ref-{i}")

    if plan.next_actions:
        st.markdown("**下一步**")
        for action in plan.next_actions:
            st.write(f"- {action}")


PLACEHOLDER = "—（請選擇）—"


def _spec_options(df: pd.DataFrame, column: str, *, numeric: bool = False) -> list[str]:
    values = df[column].dropna().unique()
    if numeric:
        values = sorted(values, key=float)
    else:
        values = sorted(map(str, values))
    return [PLACEHOLDER] + [str(v) for v in values]


def render_order_tab() -> None:
    st.subheader("📝 訂單估價")
    st.caption("填齊必填規格（標 *）後才能估價——規格不完整時，AI 結果不會準確。")
    df = _load_orders()
    results = st.session_state.setdefault("results", [])

    with st.form("order_form"):
        c1, c2, c3 = st.columns(3)
        product_family = c1.selectbox("產品族 *", _spec_options(df, "product_family"))
        core_count = c2.selectbox("芯數 *", _spec_options(df, "core_count"))
        section = c3.selectbox("截面積 mm² *", _spec_options(df, "section_area_mm2", numeric=True))

        c4, c5, c6 = st.columns(3)
        quantity = c4.number_input("數量（噸）*", min_value=0.0, step=0.5, value=0.0)
        delivery = c5.date_input("交期 *", value=date.today() + timedelta(days=30))
        urgency = c6.selectbox("急迫度", ["normal", "rush", "emergency"])

        c7, c8, c9 = st.columns(3)
        customer = c7.text_input("客戶名稱（選填）")
        customer_type = c8.selectbox("客戶類型（選填）", ["（未指定）"] + _spec_options(df, "customer_type")[1:])
        promise_type = c9.selectbox("交期類型（選填）", ["（未指定）"] + _spec_options(df, "promise_type")[1:])

        submitted = st.form_submit_button("▶ 估價")

    if submitted:
        missing = []
        if product_family == PLACEHOLDER:
            missing.append("產品族")
        if core_count == PLACEHOLDER:
            missing.append("芯數")
        if section == PLACEHOLDER:
            missing.append("截面積")
        if quantity <= 0:
            missing.append("數量")
        if missing:
            st.warning("請先填齊必填欄位：" + "、".join(missing))
        else:
            spec = OrderSpec(
                customer_name=customer or "未具名客戶",
                product_family=product_family,
                product_description=f"{product_family} {section}mm² {core_count}",
                core_count=core_count,
                section_area_mm2=section,
                quantity_ton=quantity,
                priority="緊急" if urgency != "normal" else "一般",
                customer_type=customer_type if customer_type != "（未指定）" else "一般客戶",
                promise_type=promise_type if promise_type != "（未指定）" else "標準交期",
                requested_delivery=delivery,
                urgency=urgency,
                spec_diff={},
            )
            try:
                with st.status("🤖 Agents 協調中…", expanded=True) as box:
                    st.write("🧠 思考中…")
                    st.write("🔎 檢索歷史訂單資料庫（RAG）…")
                    st.write("📊 依相似案例推估報價與交期…")
                    plan = run_orchestrator(spec=spec)
                    box.update(label="✅ 協調完成", state="complete", expanded=False)
            except Exception as exc:  # noqa: BLE001 — surface failure, keep history
                st.error(f"協調失敗：{type(exc).__name__}: {exc}")
            else:
                summary = f"{product_family} · {section}mm² · {core_count} · {quantity:g} 噸"
                results.insert(0, {"summary": summary, "plan": plan})

    if not results:
        st.info("填好規格、按「▶ 估價」後，結果會顯示在這裡。")
        return

    history = st.container(height=460)
    for i, entry in enumerate(results):
        with history.container(border=True):
            st.markdown(f"**估價結果 #{len(results) - i}** — {entry['summary']}")
            _render_plan(entry["plan"], key_prefix=f"res-{i}")


@st.cache_data
def _load_orders() -> pd.DataFrame:
    return pd.read_csv(DEFAULT_CSV_PATH, encoding="utf-8-sig")


def render_history_tab() -> None:
    st.subheader("📋 歷史訂單")
    df = _load_orders()

    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    sel_cust = c1.multiselect("客戶", sorted(df["customer"].dropna().unique()))
    sel_fam = c2.multiselect("產品族", sorted(df["product_family"].dropna().unique()))
    min_risk = c3.slider(
        "綜合風險下限",
        float(df["overall_risk_score"].min()),
        float(df["overall_risk_score"].max()),
        float(df["overall_risk_score"].min()),
    )
    high_only = c4.checkbox("只看高風險")

    filtered = df
    if sel_cust:
        filtered = filtered[filtered["customer"].isin(sel_cust)]
    if sel_fam:
        filtered = filtered[filtered["product_family"].isin(sel_fam)]
    if high_only:
        filtered = filtered[filtered["is_high_risk"] == "Y"]
    filtered = filtered[filtered["overall_risk_score"] >= min_risk]

    st.caption(f"共 {len(filtered)} 筆（點一列看完整詳情）")
    cols = [c for c in HISTORY_COLUMNS if c in filtered.columns]
    event = st.dataframe(
        filtered[cols],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )
    selected_rows = event.selection.rows
    if selected_rows:
        order_detail_dialog(filtered.iloc[selected_rows[0]].to_dict())


def main() -> None:
    status = data_status()
    if not (status.db_ready and status.csv_ready and status.chroma_ready):
        render_gate(status)
        return

    page = st.sidebar.radio(
        "頁面",
        ["📝 訂單估價", "📋 歷史訂單", "🗂️ 資料狀態"],
    )
    if page.startswith("📝"):
        render_order_tab()
    elif page.startswith("📋"):
        render_history_tab()
    else:
        render_data_status_tab(status)


main()
