# CLAUDE.md — 專案工作規則

> 這份檔案會被 Claude Code 自動載入到每個 session 的 context。所有隊員（與 Claude）都應遵守。

## 專案速覽

- **名稱：** 多 Agent 綠色供應鏈變更與產能協調系統
- **目的：** 生成式實務課程期末專題
- **團隊：** 6 人 · **截止：** 2026-06-08 前後 demo
- **完整背景：** 見 [`README.md`](README.md)
- **詳細設計：** 見 [`docs/superpowers/specs/2026-05-18-multi-agent-design.md`](docs/superpowers/specs/2026-05-18-multi-agent-design.md)

## 🔴 最重要的規則：記錄每次設計討論

**每次跟 Claude 進行設計討論 / 決策 / 腦力激盪後，session 結束前必須：**

1. 在 `docs/discussions/YYYY-MM-DD-<topic>.md` 寫一份摘要，包含：
   - 日期、參與者、討論主題
   - 主要決定（bullet 列出）
   - 未解問題 / 待辦
   - 對 README 或 spec 的影響
2. 更新 [`README.md`](README.md) 或 [`docs/superpowers/specs/`](docs/superpowers/specs/) 中受影響的段落
3. `git commit` 把這次的記錄留下

**為什麼：** 6 人團隊，討論常常只有 1–2 人在場。沒寫下來，其他隊員無法跟上。

**Claude：** 不要等使用者要求——只要這個 session 包含設計討論，主動在結束前完成上面三件事。

## 技術選型（不要任意更改）

| 層 | 工具 |
|---|---|
| LLM 介面 | LiteLLM（provider-agnostic） |
| Agent 編排 | LangGraph |
| RAG | ChromaDB |
| Backend | FastAPI |
| Frontend | Streamlit |
| Schema | Pydantic |

**LLM provider：** 預設 Gemini 1.5 Flash 免費版。每人 `.env` 自選。**不要**用 ChatGPT 訂閱（那是網頁版，不能呼叫 API）。

## 程式碼規範

- Python 3.11+，全部用 type hints
- Pydantic models 放在 `shared/models.py`，**所有 agent 間訊息一律經過 Pydantic 驗證**
- LLM 呼叫**一律**經過 `shared/llm_client.py`，不要在 agent 裡直接 `import openai` 或 `litellm`
- Agent 的 prompts 放在各自模組的 `PROMPT = """..."""` 常數，方便 review
- Commit message 英文、imperative mood、簡短
- 不要 commit `.env`、`data/`、`*.csv`、任何含真實訂單 / 客戶資料的東西

## 給 Claude 的工作守則

- **回應語言：** 預設繁體中文（與使用者主要語言一致）；程式碼註解可英文。
- **修改前先讀**：要動的檔案完整讀過再改。不要假設檔案內容。
- **範圍要緊**：3 週的專案，**不要**多加 agent、不要重構不相關的程式、不要為「未來可能用到」做設計。
- **介面優先**：改任何 agent 前，先確認 `shared/models.py` 的 schema 沒被破壞。
- **問問題**：不確定時直接問，不要猜。但問之前先 grep 一下能不能自己找到答案。

## 分工 quick reference

| 模組路徑 | 負責人角色 |
|---|---|
| `shared/`、`docs/`、整合測試 | PM / 統整 |
| `agents/*.py` | Agent 編排（2 人） |
| `pricing/*.py`、`data/` 整理 | 估價 / RAG（2 人） |
| `ui/*.py` | UI / Demo |
