# 多 Agent 綠色供應鏈變更與產能協調系統

> 生成式實務課程期末專題 · 6 人團隊 · 3 週衝刺

## 一、痛點背景

伺服器 ODM/OEM（廣達、緯創、英業達等）接 AWS / Meta / Google 等雲端大廠的客製化訂單。產業面臨以下協調困境：

1. **跨部門協調延遲**：客戶改規格 → 業務 → 工程確認 → 採購評估 → 產線重排 → 回客戶，一輪 **3–5 天**。急單常常來不及。
2. **報價憑經驗**：每張訂單客製化程度高，資深業務憑記憶 + Excel 估價，新人需 1–2 年才能準。經驗無法系統化傳承。
3. **ESG 約束爆炸**：AWS/Meta 等客戶要求碳足跡、可回收比例、供應商在地化。這些原本不在報價系統內，現在每張單都要重算。
4. **產能可見度差**：IoT 資料分散在不同系統，業務報交期時看不到即時機台狀態。

**目標：** 把 3–5 天的協調壓縮到 **5 分鐘內**，給業務一份「估價 + 交期 + 碳排 + 替代方案」的協調報告。

## 二、系統概觀

採 **Orchestrator + Specialist** 多 agent 架構，搭配 **Palantir 風格的歷史訂單 RAG 估價**。

```
            ┌─────────────────────────────────┐
   客戶單 → │     Orchestrator Agent          │
            │  （規劃要呼叫哪些專家、整合結果）│
            └────┬────┬────┬────┬─────────────┘
                 │    │    │    │
        ┌────────┘    │    │    └────────┐
        ▼             ▼    ▼             ▼
   [Order Intake] [Capacity] [Pricing] [ESG/Supplier]
   解析規格變更   查 IoT     RAG 歷史   找替代料/廠
   緊急度判讀     機台狀態   訂單估價    碳排計算
                                          │
                            ┌─────────────┘
                            ▼
                     ┌─────────────┐
                     │  Aggregator │ → 協調報告
                     └─────────────┘
```

詳細設計請見 [`docs/superpowers/specs/2026-05-18-multi-agent-design.md`](docs/superpowers/specs/2026-05-18-multi-agent-design.md)。

## 三、技術選型

| 層 | 工具 | 理由 |
|---|---|---|
| LLM 介面 | **LiteLLM** | 一套程式碼支援 OpenAI / Gemini / Claude / Ollama，每人用自己的 key |
| Agent 編排 | LangGraph | 視覺化流程好 demo |
| RAG / 向量庫 | ChromaDB | 本地跑，零設定 |
| Backend | FastAPI | Python 統一 |
| Frontend | Streamlit | 3 週做 demo 比 Next.js 快 5 倍 |
| Schema | Pydantic | Agent 間訊息契約 |
| 資料處理 | Pandas | 處理老師給的 csv |

**LLM Provider 策略**（重要）：

- ChatGPT Plus / Pro 訂閱 **無法**用於 API 呼叫，需另開 OpenAI Platform 帳號或用其他 provider。
- 預設 provider：**Gemini 1.5 Flash 免費版**（每天 1500 次請求免費，多人開發夠用）。
- 開發階段用 Gemini Flash，demo 前最後一週切 GPT-4o-mini 跑穩定版。
- 每位隊員可在 `.env` 自行設定，互不衝突。

## 四、團隊分工

| 角色 | 人數 | 負責 |
|---|---|---|
| **PM / 統整** | 1 | repo 結構、Pydantic schemas、LLM client wrapper、整合測試、demo 簡報 |
| **Agent 編排** | 2 | Orchestrator + 4 個 sub-agents、LangGraph flow、agent prompts |
| **估價 / RAG** | 2 | 歷史訂單 ingest、embeddings、retrieval、估價 prompt、補 mock data |
| **UI / Demo** | 1 | Streamlit 前端、agent 對話視覺化、demo 情境腳本 |

**PM 第一週交付物（block 整個團隊的東西）：**

- `shared/models.py` — `OrderRequest`、`AgentMessage`、`CoordinationPlan` 等 Pydantic schemas
- `shared/llm_client.py` — LiteLLM wrapper，含 retry、logging、cost tracking
- `.env.example` — 列出所有支援的 provider 設定範例
- repo 結構與 README

## 五、三週時程

| 週 | 目標 | 里程碑 |
|---|---|---|
| **W1**（5/18–5/24） | 探索老師資料、定義 schemas、agent 骨架（先用 mock LLM 回應） | end-to-end 假流程能跑 |
| **W2**（5/25–5/31） | 接真實 LLM、RAG 上線、Streamlit UI 雛形 | 單一情境完整跑通 |
| **W3**（6/1–6/7） | 整合、prompt 調校、3 個 demo 情境、簡報 | 期末 demo |

## 六、Repo 結構（規劃中）

```
.
├── README.md                       # 你在這裡
├── CLAUDE.md                       # 給 Claude Code / 隊員的工作規則
├── docs/
│   ├── superpowers/specs/          # 設計規格
│   └── discussions/                # 每次討論的記錄（重要！見 CLAUDE.md）
├── shared/
│   ├── models.py                   # Pydantic schemas
│   └── llm_client.py               # LiteLLM wrapper
├── agents/
│   ├── orchestrator.py
│   ├── order_intake.py
│   ├── capacity.py
│   ├── pricing.py
│   └── esg.py
├── scripts/
│   ├── convert_teacher_excel.py    # 老師 xlsx → RAG CSV
│   └── build_db.py                 # 老師 xlsx → SQLite（9 表）
├── pricing/
│   ├── ingest.py                   # 歷史訂單 → embeddings → ChromaDB
│   └── retrieval.py
├── shared/
│   └── data_pipeline.py            # 啟動偵測 + 轉檔串接（UI 唯一介面）
├── ui/
│   └── streamlit_app.py            # 啟動 gate + 轉檔 + 協調 panel
├── raw_data/                       # gitignore；放老師原始 xlsx
├── data/                           # gitignore；轉檔產物（SQLite / CSV）
└── tests/
```

## 七、起步

```bash
# 安裝（之後 PM 會放 requirements.txt）
pip install litellm langgraph chromadb fastapi streamlit pandas pydantic

# 設定環境變數
cp .env.example .env
# 編輯 .env，填入你自己的 LLM provider key（OpenAI / Gemini / Anthropic 擇一）

# 跑 UI
streamlit run ui/streamlit_app.py
```

## 八、討論記錄

所有設計決定都記錄在 [`docs/discussions/`](docs/discussions/)。新加入的隊員請從第一筆讀起。

## 九、各組工作指南

每個角色的詳細任務、檔案、規則：[`docs/team/`](docs/team/)

| 角色 | 文件 |
|---|---|
| PM / 統整 | [docs/team/pm.md](docs/team/pm.md) |
| Agent 編排（2 人） | [docs/team/agents.md](docs/team/agents.md) |
| 估價 / RAG（2 人） | [docs/team/pricing.md](docs/team/pricing.md) |
| UI / Demo | [docs/team/ui.md](docs/team/ui.md) |
