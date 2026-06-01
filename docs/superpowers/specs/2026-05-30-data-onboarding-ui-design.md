# 設計：資料導入 UI（啟動 gate + 轉檔）與完整 Streamlit panel

- **日期：** 2026-05-30
- **作者：** Max + Claude
- **狀態：** 待 review
- **相關：** [`docs/discussions/2026-05-26-pricing-rag-teacher-cable-data-redo.md`](../../discussions/2026-05-26-pricing-rag-teacher-cable-data-redo.md)、[`docs/team/ui.md`](../../team/ui.md)

## 背景與動機

老師提供的線纜資料是一份 9 工作表、互有外鍵的關聯式 Excel（`raw_data/線纜製造排程資料集_半年訂單.xlsx`，約 6,836 列）。這份資料含**真實客戶名稱與合約編號**，且 repo 為 **public**，因此資料**全程不進 git**。

問題：隊友 clone 下來後，沒有任何可用的資料庫 / 向量索引，必須手動跑多支 script 才能啟動系統。目標是讓 Streamlit panel **啟動時自動偵測資料狀態**，缺資料時引導使用者「把 xlsx 放進 `raw_data/` → 一鍵轉檔（含進度動畫）→ 進入主系統」。

## 目標

1. App 啟動時偵測三個資料產物是否就緒，缺則進入導入 gate。
2. 使用者把 xlsx 放進 `raw_data/` 後，一鍵觸發轉檔，全程有進度動畫。
3. 轉檔同時建立**兩種**資料儲存：關聯式 SQLite（給 Capacity/ESG）與 ChromaDB 向量索引（給 Pricing RAG）。
4. 資料齊全後進入完整主 panel（接 stub orchestrator）。

## 非目標（YAGNI）

- 不做網頁檔案上傳（`st.file_uploader`）；使用者手動放 `raw_data/` + 重新偵測即可。
- 不寫真實的 LLM orchestrator / agents（agents/ 目前是空的）——本次用 stub。
- 不把任何資料或匿名資料 commit 進 repo。
- 不改 `shared/models.py`、不改既有的 `convert_teacher_excel.py` / `pricing/ingest.py`。
- UI 不寫自動化測試（改用手動驗收清單）。

## 整體架構

```
raw_data/*.xlsx  ← 隊友自己拖進來（gitignored，永不進 repo）
      │  使用者在 panel 點「開始轉檔」
      ▼
┌─ shared/data_pipeline.py  (新增，純函式、無 UI) ─────────┐
│  data_status()      回報三個產物在不在 + 筆數            │
│  build_database()   xlsx 9 sheets → data/supply_chain.db │  ← 呼叫 scripts/build_db.py
│  convert_for_rag()  xlsx → data/teacher_orders_for_rag.csv│  ← 呼叫既有 convert_teacher_excel
│  ingest_to_chroma() CSV → ChromaDB                        │  ← 呼叫既有 ingest
│  run_full_pipeline()  依序跑上面三步，可回報每步進度     │
└──────────────────────────────────────────────────────────┘
      ▼ 三個產物（全部 gitignored）
data/supply_chain.db   data/teacher_orders_for_rag.csv   chroma_db/
      │                                                    │
   Capacity/ESG 之後用 SQL 查                       Pricing 用向量查
      ▼
ui/streamlit_app.py ── 啟動呼叫 data_status();缺資料→gate;齊全→主 panel
      │
      ▼
agents/orchestrator.py (stub) ── run_orchestrator(OrderRequest)->CoordinationPlan
```

**設計原則**：轉檔邏輯放 `shared/data_pipeline.py`（純函式、無 UI 依賴），Streamlit 只呼叫它並把進度渲染成動畫。符合「UI 不寫業務邏輯」規則，且日後若改 FastAPI/Next.js 此層可直接重用。

## 元件設計

### 1. `scripts/build_db.py`（新增）

把 9 個 sheet 轉成 SQLite，一個 sheet 一張表。

- 輸入：xlsx 路徑（預設找 `raw_data/` 下第一個 `.xlsx`）；輸出：`data/supply_chain.db`。
- 表名正規化為英文 slug（對照表寫在模組常數，例：`01_訂單需求`→`orders`、`02_產品主檔`→`products`、`05_機台週產能`→`machine_weekly_capacity`、`09_排程因素評估`→`schedule_risk` 等 9 張）。
- 欄名保留中文或正規化皆可；**MVP 保留原中文欄名**以降低風險（Capacity/ESG 組之後可再正規化）。
- 在主要 key 上建 index：`orders(訂單明細編號, 產品料號)`、`schedule_risk(訂單明細編號)`、`machine_weekly_capacity(機台編號, 週起始日)`、`products(料號)`。
- 驗證：缺 sheet 或某 sheet 為空 → 拋明確錯誤（含 sheet 名）。
- 提供 `build_database(excel_path, db_path) -> dict[str, int]`（回傳每張表列數）與 `main()`（CLI）。

### 2. `shared/data_pipeline.py`（新增）

UI 與轉檔之間的唯一介面。純函式，無 Streamlit import。

- `DataStatus`（Pydantic model 或 dataclass）：`db_ready: bool`、`csv_ready: bool`、`chroma_ready: bool`、各自的列數 / 筆數、`raw_excel_path: Path | None`。
- `find_raw_excel() -> Path | None`：找 `raw_data/` 下第一個 `.xlsx`。
- `data_status() -> DataStatus`：檢查三個產物是否存在並回報筆數。chroma 就緒判定 = persist dir 存在且 collection 有 count > 0。
- `build_database()` / `convert_for_rag()` / `ingest_to_chroma()`：各包一步，**明確傳入 `raw_data/` 的 xlsx 路徑**（注意：既有 `convert_teacher_excel.py` 預設路徑是 `data/...xlsx`，本層必須覆寫成 `raw_data/` 實際路徑）。
- `run_full_pipeline(progress_callback)`：依序跑三步，每步前後呼叫 `progress_callback(step_name, status, detail)` 讓 UI 更新動畫；任一步拋例外即停止並向上傳遞（UI 顯示 ❌ + 重試）。

### 3. `agents/orchestrator.py`（stub，新增）

- `run_orchestrator(order: OrderRequest) -> CoordinationPlan`。
- **Pricing 走真資料**：呼叫 `pricing.retrieval.retrieve_similar(query, k=3)`，把結果填入 `CoordinationPlan.reference_orders`。query 由 order 文字組成（接近 `spec_summary` 格式以提高命中，見 05-26 文件建議）。
- 其餘欄位（estimated_price、carbon_footprint_kg、estimated_delivery、capacity_status…）回傳合理罐頭值。
- retrieval 掛掉時 graceful 降級（reference_orders 給空 list + risk 註記），不讓 UI 崩。
- 標註 `# W1 stub — Agent 組 Task 6 完成後替換`，介面與真版一致。

### 4. `ui/streamlit_app.py`（新增）

啟動時 `data_status()` 分流：

**情況 A — 資料齊全** → 主 panel。

**情況 B — 缺資料且 `raw_data` 無 xlsx**：提示「請將老師 Excel 放到 `raw_data/` 後按重新偵測」+ `[🔄 重新偵測]` 按鈕。

**情況 C — `raw_data` 有 xlsx 但未轉**：顯示偵測到的檔名 + sheet 數 + 約略筆數 + `[⚙️ 開始轉檔]`。按下 → 用 `st.status` 逐步顯示三步進度（建 SQLite → 產 CSV → 建向量索引；embedding 首次需下載模型，標註約 30–60 秒）。全綠 → `st.balloons()` + 「進入系統」。任一步失敗顯示 ❌ + 訊息 + 重試。

**主 panel**（照 `docs/team/ui.md` 草圖）：
- 側欄：常駐資料狀態（DB / CSV / 向量索引 各筆數）+「重建資料」按鈕。
- 左：客戶需求輸入（Demo 情境下拉、客戶、需求 textarea、急迫度）+「▶ 跑 Agent」。
- 中：協調報告卡片（`st.metric` 報價/交期/碳排 + `st.dataframe` 參考歷史訂單）。
- 下：Agent Trace（`st.chat_message` 逐則顯示 4 個 agent）。
- 用 `st.session_state` 保存中間狀態避免 rerun 重跑。

**UI 規則**：不 import litellm、不寫業務邏輯、不 hardcode `.env`、不改 `shared/models.py`。

## 資料流

1. 啟動 → `data_status()` → 分流 gate / panel。
2. 轉檔：`run_full_pipeline` → build_db → convert → ingest，產物落地 `data/` 與 `chroma_db/`。
3. 跑 agent：輸入 → `OrderRequest` → `run_orchestrator` →（內部呼叫 `retrieve_similar`）→ `CoordinationPlan` → 渲染。

## 錯誤處理

- 轉檔每步獨立 try；失敗即停、顯示該步錯誤、提供重試，不污染後續步驟。
- embedding 慢／首次下載模型：動畫預先標註預期耗時。
- retrieval 失敗：stub 降級回罐頭，UI 不崩。
- `find_raw_excel` 找到多個 xlsx：取第一個並在 UI 提示檔名，讓使用者確認。

## 測試策略

- `tests/test_build_db.py`：fixture 用 pandas 在 tmp_path 造迷你 9-sheet xlsx（假資料、無真實客戶名），驗 9 表建出、列數對、key 有 index、可 SELECT；缺 sheet/欄位 → 明確錯誤。
- `tests/test_data_pipeline.py`：`data_status()` 三產物存在/不存在的回報；用 monkeypatch spy 三步驗串接順序與「某步失敗即停」。
- `tests/test_orchestrator_stub.py`：`run_orchestrator` 回傳合法 `CoordinationPlan`（過 Pydantic）；monkeypatch retrieval 驗有接進 reference_orders 且失敗時 graceful 降級。
- **不測** UI（改手動驗收）、不測既有 convert/ingest（已有自己的測試）。

### UI 手動驗收清單

- [ ] 無資料 + 無 xlsx → 顯示情況 B 提示
- [ ] 放 xlsx 後重新偵測 → 顯示情況 C（檔名 + sheet 數）
- [ ] 點「開始轉檔」→ 三步進度動畫逐一變綠 → balloons → 進主 panel
- [ ] 轉檔中某步失敗 → 顯示 ❌ + 重試
- [ ] 主 panel：選 demo 情境 → 跑 Agent → 看到 4 個 agent trace + 報告卡片 + 真實參考歷史訂單
- [ ] 側欄資料狀態正確；「重建資料」可回到轉檔流程

## 對 repo 的影響

- **新增**：`scripts/build_db.py`、`shared/data_pipeline.py`、`agents/orchestrator.py`、`ui/streamlit_app.py`、`tests/test_build_db.py`、`tests/test_data_pipeline.py`、`tests/test_orchestrator_stub.py`。
- **不改**：`scripts/convert_teacher_excel.py`、`pricing/ingest.py`、`pricing/retrieval.py`、`shared/models.py`。
- **`.gitignore` 補一行 `*.db`**（目前只擋 `*.sqlite3`，`supply_chain.db` 會漏進 repo——重要）。
- README 結構圖補上 `scripts/build_db.py` 與 `shared/data_pipeline.py`。

## 未解問題 / 待辦

- SQLite 欄名 MVP 保留中文；Capacity/ESG 組接手時可再決定是否正規化成英文。
- demo query normalization（把口語輸入整理成接近 `spec_summary`）目前在 stub 內最小實作，真 orchestrator 接手時再強化。
