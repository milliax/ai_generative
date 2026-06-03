# 設計：協調聊天 + 歷史訂單檢索 多 Tab UI

- **日期：** 2026-06-03
- **作者：** Max + Claude
- **狀態：** 待 review
- **相關：**
  - [`docs/superpowers/specs/2026-05-30-data-onboarding-ui-design.md`](2026-05-30-data-onboarding-ui-design.md)（前一版 UI：資料閘門 + 單一協調 panel）
  - [`docs/discussions/2026-06-01-agent-orchestrator-rag-integration.md`](../../discussions/2026-06-01-agent-orchestrator-rag-integration.md)（本次要接上的 orchestrator + RAG）

## 背景與動機

`agent-rag-teacher-data` 分支合併後，系統已具備可用功能：

- **`run_orchestrator(OrderRequest) → CoordinationPlan`**（`agents/orchestrator.py`）：單輪跑完 intake → capacity → RAG 檢索 → pricing → esg，輸出含估價、交期、產能狀態、換線風險、**參考歷史訂單**、風險與下一步。
- **`retrieve_similar(query, k) → list[dict]`**（`pricing/retrieval.py`）：對 ChromaDB 做語意檢索，回傳最相似的歷史訂單，每筆 dict 帶 `similarity` 與**全部約 45 個欄位**（客戶、產品、數量、銅重、各風險分數、`recommended_action`、`estimated_delay_days`、起訖日…）。

問題：目前 `ui/streamlit_app.py` 在資料閘門通過後只有一個**單一協調 panel**，無法獨立檢索歷史訂單，也沒有從協調結果點進參考訂單看詳情的路徑。此外該 panel 仍讀舊欄位 `plan.estimated_price` / `plan.carbon_footprint_kg`，**與合併後的 `CoordinationPlan` schema 不符，一跑就會 AttributeError**。

目標：把主畫面改成多 tab，讓「協調聊天」與「歷史訂單檢索」兩條真實功能線各自可用，並能互相連結。

## 目標

1. 資料閘門通過後，主畫面改為 3 個 tab：**資料狀態 / 協調聊天 / 歷史訂單檢索**。
2. 協調聊天：以聊天 UI 包住 `run_orchestrator`（**單輪、無記憶**），每則訊息獨立跑一次，結果含可點的參考歷史訂單。
3. 歷史訂單檢索：搜尋框直接呼叫 `retrieve_similar`，結果以卡片列出，可逐筆點進詳情。
4. 共用詳情元件：給一筆訂單 dict 就能彈出 modal 顯示完整欄位；聊天與檢索共用同一個。
5. 順手修掉現有 panel 讀錯 `CoordinationPlan` 欄位的 bug。

## 非目標（YAGNI）

- **不做多輪對話 / 記憶**：聊天框每則訊息獨立，不追問、不記上下文（之後若要再開新案）。
- **不改 `shared/models.py`、`agents/*`、`pricing/*`**：UI 只呼叫既有函式，不碰 business logic 與 schema。
- **不新增資料上傳 / 編輯**：歷史訂單唯讀。
- **不重寫資料閘門**：沿用現有 `render_gate` / `data_status` / `run_full_pipeline`。
- **不做網頁登入 / 多使用者 / 持久化對話**：對話僅存在當下 session。

## 整體架構

```
main()
 ├─ data_status() 未就緒 → render_gate()           （沿用現狀）
 └─ 就緒 → st.tabs(["🗂️ 資料狀態", "💬 協調聊天", "🔍 歷史訂單檢索"])
              ├─ tab0: render_data_status_tab(status)   （把現有 sidebar 資訊搬進來）
              ├─ tab1: render_chat_tab()
              └─ tab2: render_search_tab()
```

### 檔案分工

遵守 CLAUDE.md 的 UI 規則（`ui/*.py` 為 UI 地盤、不放 business logic、不改 schema）。新程式只**呼叫** `run_orchestrator` / `retrieve_similar`。

| 檔案 | 職責 |
|---|---|
| `ui/streamlit_app.py`（改） | page config、資料閘門、`st.tabs` 路由、`render_data_status_tab()`、`render_chat_tab()`、`render_search_tab()` |
| `ui/order_detail.py`（新） | 共用顯示元件：`render_order_detail(order)`（分組顯示欄位）、`order_detail_dialog(order)`（`@st.dialog` 彈窗）、`render_order_card(order, key)`（可點的訂單卡片/按鈕） |

界線理由：「給一筆訂單 dict → 顯示它」是聊天與檢索都要用的邏輯，獨立成一檔最乾淨；改詳情排版不影響 tab 佈局。

## 各元件設計

### Tab 1 — 協調聊天（`render_chat_tab`）

- 上方保留 **demo scenario 快捷鈕**（沿用現有 `DEMO_SCENARIOS`）；點一下把該情境文字塞進待送訊息。
- chat_input 上方放一個 `st.text_input("客戶名稱（選填）")`；空白時送出以 `"未具名客戶"` 代入。急迫度不在 UI 設，傳 `urgency=None`，由 intake agent 從文字自行判斷 rush/emergency。不為單輪聊天加整排表單欄位。
- `st.chat_input("輸入客戶需求…")` 收使用者需求文字。
- 送出流程：
  1. 組 `OrderRequest(customer=<客戶或 "未具名客戶">, raw_text=<輸入>, received_at=datetime.now(), urgency=None)`。
  2. `with st.status("🤖 Agents 協調中…")`: 呼叫一次 `run_orchestrator(order)`。
  3. 把 `{role: "user", text}` 與 `{role: "assistant", plan: <CoordinationPlan>}` 兩則 append 進 `st.session_state["chat"]`。
- 重繪：每次 rerun 從 `st.session_state["chat"]` **重新 render 已存結果**，不重跑 orchestrator（避免重複燒 LLM）。
- assistant 泡泡內容（讀**正確**的 `CoordinationPlan` 欄位）：
  - 三個 metric：💰 `estimated_price_ntd`（含 `price_confidence` 區間 caption）、📅 `estimated_delivery`、🏭 `capacity_status`
  - `changeover_risk` 文字
  - `risks`（逐條 `st.warning`）、`next_actions`（條列）
  - **📄 參考歷史訂單**：`plan.reference_orders` 可能多筆，每筆一個 `render_order_card`（按鈕標 `訂單 {order_id}（相似度 {similarity}）`）→ 點擊開詳情 modal。

### Tab 2 — 歷史訂單檢索（`render_search_tab`）

- `st.text_input("搜尋歷史訂單（規格 / 客戶 / 描述）")` + `st.slider` 選 k（1–10，預設 5）。
- 送出 → `with st.spinner`: `retrieve_similar(query, k)`，結果存 `st.session_state["search_results"]`。
- 從 session_state render 卡片清單；每張卡片 `render_order_card` → 點 `查看詳情` 開同一個 modal。
- 空查詢提示「輸入關鍵字後搜尋」；查無結果顯示 caption。

### 共用詳情（`ui/order_detail.py`）

- `render_order_detail(order: dict)`：把欄位**分組**顯示（缺的欄位略過，不假設一定存在）：
  - **基本資訊**：order_id、customer、order_date、due_date、quantity_ton、copper_kg
  - **規格**：product_description、product_family、core_count、section_area_mm2、promise_type、customer_type
  - **風險評分**：overall_risk_score、capacity_risk_score、changeover_risk_score、due_pressure_score、estimated_delay_days、is_high_risk
  - **建議與摘要**：recommended_action、matched_summary（或 spec_summary）、similarity（若有）
- `order_detail_dialog(order)`：`@st.dialog("訂單詳情")` 包住 `render_order_detail`。
- `render_order_card(order, key)`：顯示精簡摘要 + 一顆按鈕；按下 → 呼叫 dialog。
  - 欄位分組以小工具函式 `group_order_fields(order) -> dict[str, list[tuple[label, value]]]` 完成，**此函式為純資料整理、可單元測試**。

## 資料流

```
[聊天] 使用者文字
   → OrderRequest → run_orchestrator → CoordinationPlan
   → 存 session_state["chat"] → render 泡泡 + reference_orders 卡片
        → 點卡片 → order_detail_dialog(reference dict)   ← reference dict 已含全欄位，免再查 DB

[檢索] 查詢字串 + k
   → retrieve_similar → list[dict]
   → 存 session_state["search_results"] → render 卡片清單
        → 點卡片 → order_detail_dialog(result dict)
```

關鍵：RAG 回傳的 dict 已含該訂單全部欄位，**聊天與檢索的詳情共用同一條 render 路徑，不需額外查 SQLite**。

## 錯誤處理

- `run_orchestrator` 內部已對 RAG 失敗做 fallback（pricing 改用噸數公式）；UI 不重複攔。若整段呼叫拋例外，用 `st.error` 顯示訊息、保留既有對話。
- `retrieve_similar` 若因 RAG 依賴缺失/索引未建而拋錯，`st.error` 提示「請先在資料狀態頁完成轉檔」。
- 詳情顯示對缺欄位以 `.get` 容錯，不因某欄位不存在而崩潰。

## 測試

- **純函式單元測試**（`tests/test_ui_order_detail.py`）：`group_order_fields` 給定一個含/缺部分欄位的 dict，驗證分組正確、缺欄位被略過。
- **Streamlit render 不寫自動化測試**：以手動驗收清單確認（沿用前一版 UI 的做法）。
- 手動驗收：
  1. 跑 `./run.sh`，資料閘門通過後看到 3 個 tab。
  2. 聊天 tab 送一筆訂單 → 出現協調泡泡 + 參考訂單卡片 → 點卡片彈出詳情。
  3. 重繪（如切 tab 再切回）→ 對話還在、未重跑 LLM。
  4. 檢索 tab 搜尋 → 出現卡片 → 點進詳情。
  5. 確認舊的 `estimated_price` AttributeError 不再出現。

## 對 README / 既有檔案的影響

- `README.md`：更新 UI 段落，說明三個 tab。
- `ui/streamlit_app.py`：`render_main_panel` 被 `render_chat_tab` 取代；`render_sidebar` 內容併入 `render_data_status_tab`。
