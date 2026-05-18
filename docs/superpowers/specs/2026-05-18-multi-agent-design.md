# 設計規格：多 Agent 綠色供應鏈變更與產能協調系統

**日期：** 2026-05-18
**狀態：** Draft，待團隊審閱
**作者：** Max（與 Claude 共筆）

---

## 1. 問題背景

### 產業情境

伺服器 ODM/OEM（廣達、緯創、英業達）接 AWS / Meta / Google 的客製化訂單。每張訂單規格不同（CPU 世代、記憶體配置、機殼尺寸、散熱方案），需求變動頻繁。

### 核心痛點

1. **跨部門協調延遲**：客戶改規格 → 業務 → 工程確認 → 採購評估 → 產線重排 → 回客戶。傳統流程一輪 **3–5 天**，急單來不及。
2. **報價憑經驗**：每張訂單客製化程度高，業務憑記憶 + Excel 估價，新人需 1–2 年才能準。經驗無法系統化傳承。
3. **ESG 約束**：AWS/Meta 要求碳足跡報告、可回收比例、供應商在地化。原本不在報價系統內，現在每張單都要重算。
4. **產能可見度差**：IoT 資料分散，業務報交期看不到即時機台狀態。

### 系統目標

把 3–5 天的協調壓縮到 **5 分鐘內**，給業務一份「估價 + 交期 + 碳排 + 替代方案」的協調報告。

---

## 2. 範圍

### 涵蓋（A + B）

- **A. 多 Agent 協調**：Orchestrator + 專業 agents 分工處理規格解析、產能查詢、估價、ESG 評估
- **B. 智慧估價（Palantir 風格）**：對歷史訂單做 RAG，估出新訂單的價格 + 交期 + 碳排，並**附參考案例**讓業務理解推理

### 不涵蓋（明確排除）

- 實際下單給供應商的 transaction（只到「建議」階段）
- 多 agent 互相辯論 / 投票機制（C 方案太複雜）
- 真實 IoT 連線（用 mock data 模擬 stream）
- 用戶認證、權限管理（demo 不需要）

---

## 3. 系統架構

### 高階流程

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
                            ↓
                  Streamlit UI（agent 對話可視化 + 最終建議）
```

### Agent 職責

| Agent | 輸入 | 輸出 | 主要邏輯 |
|---|---|---|---|
| **Orchestrator** | `OrderRequest` | 規劃哪些 agent 要呼叫、整合結果 | LangGraph state machine；判斷需要哪些 agent；處理資訊不足要回頭問的情境 |
| **Order Intake** | 客戶原始需求文字 / 表單 | 結構化 `OrderSpec`（規格 diff、數量、交期、急迫度） | LLM 解析自然語言；偵測規格變更類型 |
| **Capacity** | `OrderSpec` | 機台可用度、預估產線時數 | 查 IoT mock data；計算 loading；判斷是否需外援 |
| **Pricing** | `OrderSpec` + Capacity 結果 | 估價 + 交期 + **3 筆相似歷史訂單** | RAG over ChromaDB；LLM 看規格 diff vs 歷史推估 |
| **ESG/Supplier** | `OrderSpec` + BOM | 碳足跡、可回收比例、替代供應商 | 查供應商表、材料 ESG 屬性；LLM 推薦替代方案 |
| **Aggregator** | 所有 agent 結果 | `CoordinationPlan`（給業務看） | 整合 + 衝突解決（例如：產能不足時的建議） |

### 估價 Agent 細節（Palantir 風格的重點）

**這是 B 的核心，也是最有 demo 亮點的部分。**

1. **資料準備**：歷史訂單 → 把 `(規格摘要, BOM, 客戶, 數量, 最終報價, 交期, 碳排)` 做成一段文字 → embedding → ChromaDB
2. **檢索**：新訂單規格 → embedding → top-5 相似案例
3. **推理**：把 5 筆案例 + 新訂單規格丟給 LLM，prompt 結構：
   ```
   你是資深業務，看下面 5 筆歷史訂單，推估這張新單的價格、交期、碳排。
   說明：
   - 新單與哪幾筆最像、像在哪、差在哪
   - 差異對價格的影響（材料漲跌、數量、急迫度溢價）
   - 最終建議：價格 ± 信心區間
   ```
4. **輸出**：價格 + 信心 + **3 筆參考案例**（讓業務看「為什麼是這個價」）

**Demo 賣點：** 不只給數字，給「show your work」——這是 Palantir 介面的精髓。

---

## 4. 共用介面（PM 第一週交付）

### Pydantic Schemas（`shared/models.py`）

```python
class OrderRequest(BaseModel):
    customer: str
    raw_text: str                    # 客戶原始需求
    received_at: datetime
    urgency: Literal["normal", "rush", "emergency"] | None = None

class OrderSpec(BaseModel):
    cpu_sku: str
    memory_gb: int
    storage_tb: int
    chassis: str
    quantity: int
    requested_delivery: date
    spec_diff: dict[str, Any]        # vs 上次訂單的差異
    urgency: Literal["normal", "rush", "emergency"]

class AgentMessage(BaseModel):
    from_agent: str
    to_agent: str | None             # None 表示送回 orchestrator
    payload: dict[str, Any]
    reasoning: str                   # LLM 的推理過程（給 UI 顯示）

class CoordinationPlan(BaseModel):
    estimated_price: float
    price_confidence: tuple[float, float]
    estimated_delivery: date
    carbon_footprint_kg: float
    capacity_status: str
    alternative_suppliers: list[dict]
    reference_orders: list[dict]     # Palantir 風格：show your work
    risks: list[str]
    next_actions: list[str]
```

### LLM Client（`shared/llm_client.py`）

```python
from litellm import completion
import os

def call_llm(messages: list[dict], model: str | None = None, **kwargs) -> str:
    model = model or os.getenv("LLM_MODEL", "gemini/gemini-1.5-flash")
    # 包 retry、logging、cost tracking
    ...
```

`.env.example`：
```bash
LLM_MODEL=gemini/gemini-1.5-flash
GEMINI_API_KEY=
# 或：
# LLM_MODEL=gpt-4o-mini
# OPENAI_API_KEY=
# 或：
# LLM_MODEL=anthropic/claude-haiku-4-5
# ANTHROPIC_API_KEY=
```

---

## 5. 三週時程

| 週 | 目標 | 交付 |
|---|---|---|
| **W1** 5/18–5/24 | 探索老師資料；定義所有 schemas；建 LLM client；每個 agent 寫骨架（先回 mock LLM 結果） | repo 結構完整、end-to-end 假流程能跑 |
| **W2** 5/25–5/31 | Agents 接真實 LLM；估價 RAG 上線（資料 ingest + 檢索 + 推理）；Streamlit UI 雛形 | 單一情境完整跑通（規格變更 → 5 分鐘出協調報告） |
| **W3** 6/1–6/7 | 整合測試；prompt 調校；準備 3 個 demo 情境；簡報 | 期末 demo |

### 三個 Demo 情境（W3 要演的）

1. **正常單**：新客戶送來一份 RFQ → agent 跑完 → 業務拿到報價 + 交期 + 碳排
2. **急單**：客戶要兩週內 5000 台 → 產能不足 → ESG agent 找替代供應商 → 比較自製 vs 外包成本
3. **規格變更**：原訂單客戶臨時把 CPU 換代 → 系統算出新價格 + 對交期影響 + ESG 變化

---

## 6. 團隊分工

| 角色 | 人 | 模組 | 主要交付 |
|---|---|---|---|
| **PM / 統整** | 1 | `shared/`、`docs/`、整合測試、CI | Schemas、LLM wrapper、demo 簡報、整合驗證 |
| **Agent 編排** | 2 | `agents/` | Orchestrator + 4 agents 的 prompts、LangGraph flow |
| **估價 / RAG** | 2 | `pricing/`、`data/` | 歷史訂單 ingest、embeddings、retrieval、估價推理 prompt、補 mock data |
| **UI / Demo** | 1 | `ui/` | Streamlit 前端、agent 對話視覺化、demo 腳本 |

### 第一週**必達**里程碑

- [ ] PM 交付 `shared/models.py` + `shared/llm_client.py` + `.env.example`（**block 整個團隊**，必須最遲 5/21 完成）
- [ ] 估價組從老師資料抽出 50+ 筆訂單，先手動分析資料欄位
- [ ] Agent 組畫出 LangGraph state machine 草圖（哪些 agent 在哪些情境會被呼叫）
- [ ] UI 組做 Streamlit 雛形（先用假資料把畫面排出來）

---

## 7. 風險與緩解

| 風險 | 緩解 |
|---|---|
| 老師資料拿到太晚 / 不完整 | W1 就開始補 mock data；schema 設計成資料補齊後容易換 |
| LLM cost 燒太快 | 開發用 Gemini Flash 免費版；agent 之間用快取 + 結構化輸出減少 token |
| 6 人並行衝突 | PM 第一週鎖死介面；各模組對 schemas 寫單元測試 |
| Agent 行為不穩定 | 所有 LLM 輸出都用 Pydantic 驗證；失敗時降級到 deterministic fallback |
| Demo 前 LLM provider 出包 | LiteLLM 讓我們能快速切到備援 provider |

---

## 8. 未解問題（給團隊討論）

- [ ] 老師會給什麼資料欄位？欄位齊全度如何？（5/19 前確認）
- [ ] 要不要把 demo 流程錄成 video 當備案，避免 demo 當天 LLM API 出包？
- [ ] 簡報語言：中文 or 英文？老師偏好？
- [ ] 系上有沒有 OpenAI credit / GCP credit 可以申請？

---

## 9. 下一步

1. 團隊 review 此 spec（特別注意第 8 節未解問題）
2. PM 開始寫 `shared/models.py`、`shared/llm_client.py`
3. 估價組接觸老師拿資料
4. 進入 implementation plan（每週 PR 切分、每個 agent 的 prompt 結構細節）
