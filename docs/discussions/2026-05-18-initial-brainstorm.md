# 討論記錄：初版 brainstorm 與系統設計

**日期：** 2026-05-18
**參與者：** Max（+ Claude）
**主題：** 期末專題範圍、架構、技術選型、分工

## 主要決定

### 範圍
- 焦點 = **A（多 agent 協調流程）+ B（Palantir 風格估價）**
- 不做 C（即時 IoT 動態重排）— 3 週做不完
- IoT 用 mock data 模擬，不接真實設備

### 架構
- **Orchestrator + 4 個 Specialist agents**（Order Intake / Capacity / Pricing / ESG）+ Aggregator
- 不採 linear pipeline（不靈活）、不採 multi-agent debate（太複雜）
- 估價 agent 用 RAG（ChromaDB）over 歷史訂單，輸出時附 3 筆參考案例（Palantir 風格 "show your work"）

### 技術選型
- **LiteLLM** 統一 LLM 介面（不綁死任何 provider）
- **LangGraph** agent 編排（視覺化好 demo）
- **ChromaDB** RAG
- **FastAPI** 後端 + **Streamlit** 前端（3 週速度優先，不用 Next.js）
- **Pydantic** schemas
- 預設 LLM = **Gemini 1.5 Flash 免費版**（每天 1500 次請求免費），demo 前一週切 GPT-4o-mini

### 重要釐清：ChatGPT 訂閱 ≠ OpenAI API
- ChatGPT Plus / Pro 訂閱是網頁版，**不能**用程式呼叫
- 要用 OpenAI 必須另開 platform.openai.com 帳號儲值
- 因此選擇 LiteLLM——隊員可各自用 OpenAI / Gemini / Claude / Ollama，互不影響

### 分工（6 人）
- **1 PM / 統整**：repo、Pydantic schemas、LLM client、整合測試、demo 簡報
- **2 Agent 編排**：Orchestrator + 4 sub-agents 的 prompts、LangGraph flow
- **2 估價 / RAG**：歷史訂單 ingest、embeddings、retrieval、估價 prompt、補 mock data
- **1 UI / Demo**：Streamlit、agent 對話視覺化、demo 情境腳本

### 時程
- **W1**（5/18–5/24）：探索資料、定義 schemas、agent 骨架
- **W2**（5/25–5/31）：接真實 LLM、RAG 上線、UI 雛形
- **W3**（6/1–6/7）：整合、調校、3 個 demo 情境、簡報

### Demo 三情境
1. 正常單：RFQ → 5 分鐘出協調報告
2. 急單：產能不足 → 找替代供應商
3. 規格變更：CPU 換代 → 算新價 + 交期 + ESG 影響

### 工作流程規則（重要）
- 每次跟 Claude 的設計討論，**結束前必須**寫進 `docs/discussions/`，並更新 README/spec
- 此規則寫進 `CLAUDE.md` 自動套用所有 session 與所有隊員

## 未解問題

- [ ] 老師會給什麼資料？欄位完整度？（5/19 前找老師確認）
- [ ] 簡報語言（中 or 英）？
- [ ] 系上有沒有 OpenAI / GCP credit 可申請？
- [ ] PM 角色由誰擔任？其他 5 個位置如何分配？

## 待辦

- [ ] 團隊內部 review `README.md` + `CLAUDE.md` + `docs/superpowers/specs/2026-05-18-multi-agent-design.md`
- [ ] PM 開始 W1 工作：`shared/models.py`、`shared/llm_client.py`、`.env.example`
- [ ] 估價組接觸老師拿資料
- [ ] 進入 implementation plan（細到每個 agent 的 prompt 結構、每週 PR 切分）

## 對 README / Spec 的影響

- 第一版 README、CLAUDE.md、設計 spec 都根據本次討論建立
- 沒有需要回頭修改的段落
