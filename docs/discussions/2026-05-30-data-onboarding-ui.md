# 2026-05-30 資料導入 UI 與轉檔流程實作

## 參與者
- Max、Claude

## 主題
實作啟動時的資料導入 gate + 轉檔（xlsx → SQLite + ChromaDB）+ 完整 Streamlit panel（接 stub orchestrator）。

## 主要決定
- 資料全程不進 repo（public repo + 真實客戶資料）；`.gitignore` 已含 `*.db`。
- 老師原始 xlsx 放 `raw_data/`（gitignored），轉檔產物放 `data/`（gitignored）。
- 轉檔邏輯放 `shared/data_pipeline.py`（純函式、無 Streamlit），UI 只呼叫。
- 一鍵轉檔同時建立：`data/supply_chain.db`（9 表、給 Capacity/ESG SQL）與 ChromaDB（給 Pricing RAG）。
- SQLite 一表一 sheet，欄名 MVP 保留中文。
- stub orchestrator 的 Pricing 段走真實 `retrieve_similar`，其餘欄位罐頭；以 `next_actions` + UI caption 標示為 W1 stub，避免 0.0 被誤讀為真實報價。

## 實作（feat/data-onboarding-ui 分支）
- `scripts/build_db.py` — xlsx 9 sheets → SQLite（key 上建 index）
- `shared/data_pipeline.py` — `data_status()` / `run_full_pipeline()` 三步串接 + 進度 callback
- `agents/orchestrator.py` — W1 stub，接真實 pricing RAG，retrieval 失敗 graceful 降級
- `ui/streamlit_app.py` — 啟動 gate（缺資料引導放 xlsx + 重新偵測 / 一鍵轉檔動畫）+ 主 panel
- 測試：build_db(4) + data_pipeline(7) + orchestrator(2)，全 suite 綠

## review 抓到並修掉的問題
- `_csv_row_count` 用 utf-8 開檔，但 CSV 是 utf-8-sig（BOM）→ 改為 utf-8-sig，補一個 BOM 測試。
- Streamlit `on_click=st.rerun` 會誤觸發 → 改為 `if st.button(): st.rerun()`。
- 硬寫「9 工作表 3000 筆」caption → 改為「（預期…）」措辭。

## 對 spec / README 的影響
- 依 `docs/superpowers/specs/2026-05-30-data-onboarding-ui-design.md` 實作。
- README 結構圖補上 `scripts/build_db.py`、`shared/data_pipeline.py`、`raw_data/`。

## 待辦
- Agent 組 Task 6 完成後，用真 orchestrator 替換 stub（介面 `run_orchestrator(OrderRequest)->CoordinationPlan` 已對齊）。
- Capacity/ESG 接手後決定 SQLite 欄名是否正規化成英文。
- W2：UI 補 agent trace 底部面板、streaming。
