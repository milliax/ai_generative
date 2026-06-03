# 2026-06-01 Agent Orchestrator / RAG 整合紀錄

## 主題
將 agents orchestration 與 teacher-data RAG pipeline 串接，並補上 LLM fallback。

## 已完成
- 新增 OrderIntake / Capacity / Pricing / ESG / Orchestrator agents。
- `test_smoke.py` 可跑正常單、急單、過載單。
- 建立 ChromaDB 後，RAG 可回傳 3 筆 reference orders。
- 無 Gemini API key 時，PricingAgent 不再 crash，會保留 RAG reference orders 並改用 fallback 公式。
- DB 未建立或 RAG 無結果時，也可 fallback 跑完整流程。

## 驗證
- `python -m pricing.ingest` 成功 ingest 3000 筆至 `historical_orders`。
- `python -m tests.test_smoke` 在無 API key 情況下可完成。
- 正常單與急單產能為 OK，過載單為 OVERLOAD。
- 無 API key 時會看到 LiteLLM missing key warning，但流程會 fallback 完成。

## 決策
- `data/`、Excel、CSV、`chroma_db/` 不進 Git。
- API key 不進 Git，由執行者本機環境變數提供。
- PricingAgent 優先使用 RAG reference orders；LLM 失敗時保留 reference orders 並回傳 fallback 估價。
- 後續若要 demo LLM reasoning，再於 terminal 設定 `GEMINI_API_KEY` 或 `GOOGLE_API_KEY`。

## 待辦
- 將 pricing_mode / warning 顯示到 smoke output 或 UI。
- 調整 query normalization，讓使用者口語輸入更接近 `spec_summary`。
- 若 demo 需要完整報價理由，測試有 API key 的 RAG + LLM 路徑。