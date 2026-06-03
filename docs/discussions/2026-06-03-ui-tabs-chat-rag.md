# 討論：多 Tab UI（協調聊天 + 歷史訂單檢索）

- **日期：** 2026-06-03
- **參與者：** Max + Claude
- **主題：** 把 orchestrator 與 RAG 檢索接到 Streamlit UI，讓使用者實際操作

## 背景

`agent-rag-teacher-data` 分支合併進 main 後，系統已有可用的 `run_orchestrator` 與
`retrieve_similar`，但 UI 在資料閘門後只有一個單一協調 panel，且該 panel 仍讀舊的
`CoordinationPlan` 欄位（`estimated_price` / `carbon_footprint_kg`），跑下去會 AttributeError。

## 主要決定

- 主畫面改成 **3 個 tab**：資料狀態 / 協調聊天 / 歷史訂單檢索。
- **協調聊天為單輪、無記憶**（每則訊息獨立跑一次 orchestrator）。多輪/記憶列為之後再做，
  避免動到 W1 還在 stub 的 agent 介面。
- RAG 回傳的 dict 已含整筆訂單欄位，因此**聊天的「參考歷史訂單」與檢索 tab 共用同一個詳情
  元件**，點進詳情不需另查 SQLite。
- 共用顯示元件獨立成 `ui/order_detail.py`（`render_order_detail` / `order_detail_dialog` /
  `render_order_card` / 純函式 `group_order_fields`）。
- UI 只呼叫既有函式，不改 `shared/models.py`、`agents/*`、`pricing/*`。
- 順手修掉舊 panel 讀錯 `CoordinationPlan` 欄位的 bug。
- 另外（非本主題）：修了 `streamlit run` 找不到 `agents`/`shared` 的 sys.path 問題，並加了
  `run.sh` 一鍵啟動。

## 產出

- 設計 spec：[`docs/superpowers/specs/2026-06-03-ui-tabs-chat-rag-design.md`](../superpowers/specs/2026-06-03-ui-tabs-chat-rag-design.md)
- 實作：`ui/streamlit_app.py`（改）、`ui/order_detail.py`（新）、`tests/test_ui_order_detail.py`（新）
- README UI 段落更新

## 未解 / 待辦

- 多輪對話（追問「數量改 80 噸呢？」）尚未做，等 W2 agent 接真實 LLM 後再評估。
- Order Intake / Capacity / ESG 仍是 W1 stub；聊天結果的解析品質受此限制。
- 互動流程（點卡片開 modal）只做了 app 啟動驗證，完整點擊驗收待隊友在瀏覽器手動確認。
