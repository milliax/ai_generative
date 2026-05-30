# 2026-05-26 Pricing / RAG 改用老師線纜資料重做紀錄

## 參與者

- CHIH YU YANG

## 主題

Pricing / RAG 組重新以老師提供的線纜製造排程資料完成 Task 7 與 Task 8。

## 背景

原本 Task 7 / Task 8 是以 CPU SKU、memory、storage、final_price、carbon_kg 等伺服器 mock data 為基礎。  
但老師已提供正式的線纜製造排程 Excel 資料，因此本組決定重新對齊老師資料，將 Pricing / RAG 的資料來源改為線纜訂單、產品主檔與排程風險資料。

## 主要決策

- Task 7 改為「老師線纜 Excel 資料轉換器」。
- Task 8 改為「老師線纜資料 RAG ingest / retrieval pipeline」。
- `spec_summary` 作為 embedding 用的主要文字欄位。
- 其他訂單、產品、風險欄位作為 ChromaDB metadata。
- ChromaDB collection 名稱維持 `historical_orders`。
- `data/`、Excel、CSV、`chroma_db/` 不進 Git。
- 不修改 `shared/models.py`，RAG 結果仍以 `dict[str, Any]` 回傳，方便後續 agent 整合。
- ingest 階段不呼叫 LLM，只使用 sentence-transformers embedding。

## 已完成項目

- `scripts/convert_teacher_excel.py`
  - 將老師 Excel 轉成 `data/teacher_orders_for_rag.csv`
  - 固定輸出欄位 schema
  - 檢查必要欄位、唯一鍵、merge 品質
  - 產生 `spec_summary`

- `pricing/ingest.py`
  - 讀取 `teacher_orders_for_rag.csv`
  - 使用 `spec_summary` 建立 embedding
  - 將 metadata 寫入 ChromaDB

- `pricing/retrieval.py`
  - 提供 `retrieve_similar(query, k=5)`
  - 回傳相似歷史訂單 metadata、`matched_summary` 與 `similarity`

- 測試檔案
  - `tests/test_convert_teacher_excel.py`
  - `tests/test_pricing_ingest.py`
  - `tests/test_pricing_retrieval.py`

## 驗證結果

- `python -m ruff check pricing scripts tests` 通過。
- `python -m pytest` 通過，共 27 個測試。
- 實際老師資料 end-to-end 測試通過：
  - 成功轉換 3000 筆線纜訂單資料。
  - 成功 ingest 3000 筆資料到 ChromaDB collection `historical_orders`。
  - `retrieve_similar()` 成功回傳 top-k 相似歷史訂單。

## RAG 查詢格式提醒

實測發現，若直接用口語化急單描述查詢，結果仍可用，但 similarity 可能偏低。  
若使用資料庫中既有的 `spec_summary` 格式查詢，top-1 可正確命中原始訂單，similarity 可達 1.0。

因此後續 Order Intake、Orchestrator 或 Pricing Agent 整合時，建議先將使用者輸入整理成接近 `spec_summary` 的結構化查詢，再呼叫 `retrieve_similar()`。

建議 query normalization 至少包含：

- 產品族群
- 產品描述或產品料號
- 芯數
- 截面積
- 需求數量
- 優先等級或急迫程度
- 客戶類型
- 承諾類型
- 交期壓力或延誤風險描述

## 後續待辦

- 尚未串接 Pricing Agent。
- 尚未串接 UI。
- 尚未設計最終 prompt。
- 後續若 demo 情境仍保留「估價」字樣，需要再確認線纜資料如何對應估價、交期與風險說明。
