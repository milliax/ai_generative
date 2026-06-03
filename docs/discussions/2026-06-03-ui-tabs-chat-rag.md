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

- Order Intake / Capacity / ESG 仍是 W1 stub。
- 互動流程（點卡片開 modal）只做了 app 啟動驗證，完整點擊驗收待隊友在瀏覽器手動確認。

## 追加（同日，實際試用後的修正）

Max 在瀏覽器實際操作後回報三個問題並做了流程調整：

- **中文問、英文答**：orchestrator 的 `next_actions` 與 overload 風險訊息、pricing 的 warning 都是寫死英文 → 已全部中文化。
- **怎麼問單價都一樣 / 信任度低 / 給不出參數**：
  - 顯示用的單價是 `數量(噸) × 85000` 公式，而 W1 intake stub 看不懂「2KM / 22mm」這種長度單位，數量一律 fallback 成 10 噸 → 所以單價不變。
  - LLM 其實有產出真正的中文估價分析，但 `_aggregate` 沒把 `llm_analysis` 放進 `CoordinationPlan`，被丟掉了。
- **切頁面回答消失**：使用者訊息在 LLM 呼叫前就先寫入，切頁面中斷該 run → 留下沒答案的孤兒。

**因此把協調頁從「自由聊天」改成「結構化表單 + 必填門禁」**（Max 拍板）：

- 規格表單（產品族 / 芯數 / 截面積下拉值**直接取自歷史 CSV 的真實值**，例如產品族 CV/CVV/FR-CV/HR/IV/VV/OTHER、芯數 單芯/多芯）；必填欄位填齊才能按「估價」，避免不完整資料餵給 AI。
- `run_orchestrator` 新增 `spec: OrderSpec` 參數，表單直接建好 `OrderSpec` 餵進去、**跳過 W1 intake stub**；舊的 `request` 路徑與 smoke test 維持不變（向後相容）。
- `CoordinationPlan` 新增 optional 欄位 `llm_analysis`，UI 在「🧠 AI 估價分析」顯示 LLM 真實中文分析。

**仍待處理：**

- 上方「預估單價」metric 仍是公式粗估；要把 LLM 文字裡的建議單價抽回數值欄位是另一段 parsing，未做。
- RAG 相似度偏低（top similarity 接近 0）——檢索品質調校，屬估價 / RAG 組。
