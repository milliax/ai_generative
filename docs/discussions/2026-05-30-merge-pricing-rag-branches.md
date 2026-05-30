# 2026-05-30 合併 Pricing / RAG 兩條分支進 main

## 參與者

- Max（PM / 統整）
- Claude

## 主題

估價 / RAG 組推了兩條分支到 `origin`，需驗證正確性並合併進 `main`：

- `pricing-rag-task7-mock-data`
- `pricing-rag-teacher-data-redo`

## 背景

兩條分支都從同一個 `main`（305e624）長出、彼此獨立，且**都改了同一套 `pricing/ingest.py` 與 `pricing/retrieval.py`**（同樣的公開函式 `retrieve_similar`、同樣的 ChromaDB collection `historical_orders`），因此直接兩條都合併必然在這兩個檔衝突。

- `task7-mock-data`：mock 伺服器訂單產生器（CPU / memory / storage 等）+ 以 mock 資料為基礎的 pricing RAG。
- `teacher-data-redo`：依老師正式提供的線纜製造排程 Excel 重做 RAG（見 `2026-05-26-pricing-rag-teacher-cable-data-redo.md`），定位就是**取代** mock 版 pricing。

## 驗證結果（合併前）

用專案 `.venv`（chromadb 1.4.1）實跑兩條分支測試：

- `task7-mock-data`：**45 passed**
- `teacher-data-redo`：**27 passed**

兩條都符合規範：未修改 `shared/models.py`、pricing 模組未直接 `import openai/litellm`（此 pipeline 不呼叫 LLM，只用 sentence-transformers embedding）、無真實資料 / `.env` / CSV 進 Git（`.gitignore` 已涵蓋 `data/`、`*.csv`、`*.xlsx`、`chroma_db/`）。

> 註：`shared/models.py` 目前**沒有** `PriceEvidence` 類別；兩條分支的 `retrieve_similar()` 都回傳 `list[dict]`，非 Pydantic 模型。

## 主要決策

- **`teacher-data-redo` 取代 mock 版 pricing**（依 05-26 的組內決定）。衝突的 `pricing/ingest.py`、`pricing/retrieval.py` 一律取 teacher 版。
- **保留** task7 的 `scripts/generate_mock_orders.py` 與 `tests/test_mock_data.py`（mock 產生器本身獨立、可留作工具）。
- **移除** task7 的 `tests/test_pricing_rag.py`：它測的是已被取代的 mock pricing RAG，import teacher 版模組會直接壞掉。

## 執行

1. `git merge --no-ff origin/pricing-rag-task7-mock-data`（乾淨）→ 4a9f6db
2. `git merge --no-ff origin/pricing-rag-teacher-data-redo`，衝突取 teacher 版 + `git rm tests/test_pricing_rag.py` → d0e6f6f
3. 合併後完整測試：**36 passed**（teacher 27 + mock_data 9）。`requirements.txt` 已含 `openpyxl>=3.1.0`。

最終 `tests/`：`test_convert_teacher_excel.py`、`test_mock_data.py`、`test_pricing_ingest.py`、`test_pricing_retrieval.py`。

## 未解問題 / 待辦

- **mock 產生器已成孤兒**：`generate_mock_orders.py` 產出的是舊的伺服器欄位（cpu_sku / memory_gb / storage_tb），**無法**被 teacher 版 ingest（需 `order_id` + `spec_summary`）直接吃。要嘛之後讓它輸出 `spec_summary` 格式，要嘛確定不用就刪掉。
- **retrieval 介面未 Pydantic 化**：`retrieve_similar()` 回傳 `list[dict]`。串接 Pricing Agent 時建議在邊界包一層驗證過的 schema（組內 todo 已列）。
- **尚未 push 到 `origin/main`**（本次只在本地合併）。要不要 push 待 Max 決定。
- 開發環境需 `pip install -r requirements.txt`（含新加的 `openpyxl`、既有的 `chromadb`）才能跑測試；目前 base anaconda env 沒裝，要用專案 `.venv`。

## 對 README / spec 的影響

- 估價 / RAG 的資料來源由 mock 伺服器訂單改為老師線纜訂單（已記於 05-26 文件）。`README.md` 的 `pricing/` 結構與路徑仍正確，未改動。
