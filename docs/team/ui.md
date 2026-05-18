# UI / Demo 組 工作指南

> 1 人。負責 Streamlit 前端、agent 對話視覺化、demo 情境。

## 你的定位

你做的是**demo 那天觀眾看到的東西**。技術上可能比另外兩組簡單，但**demo 給分高低 80% 看你**——一樣的後端，UI 做得好讓老師覺得「哇」，做得差就是另一個 hackathon 作品。

## 你可以依賴的東西（PM 已交付）

```python
from shared.models import OrderRequest, CoordinationPlan, AgentMessage
from agents.orchestrator import run_orchestrator   # ← 等 Agent 組 Task 6 完成才有
```

## W1 你的處境：等 Agent 組

你的 Task 9（Streamlit scaffold）要 import `run_orchestrator`，所以**你被 Agent 組的 Task 6 卡住**。預期 5/22–5/23 才會 unblock。

### 在等的期間（5/19 – 5/22）

#### 1. 設計 UI 草圖

掃過幾種 layout，挑一個跟團隊敲定：

```
┌─────────────────────────────────────────────────────────┐
│  多 Agent 綠色供應鏈協調系統                              │
├──────────────────────┬──────────────────────────────────┤
│ [左] 客戶需求輸入區     │ [中] 協調報告卡片                  │
│                      │                                  │
│ 客戶: AWS            │ 💰 預估報價: $51,200,000          │
│ 需求: Need 1000 ...  │ 📅 交期: 2026-08-15              │
│ 急迫度: rush ▼       │ 🌱 碳排: 120,000 kg              │
│ [▶ 跑 Agent]         │                                  │
│                      │ 📊 參考歷史訂單（為何是這個價）     │
│                      │ ┌─────────────────────────┐      │
│                      │ │ HIST-001  0.92  $50.2M  │      │
│                      │ │ HIST-007  0.87  $52.5M  │      │
│                      │ │ HIST-023  0.81  $49.8M  │      │
│                      │ └─────────────────────────┘      │
├──────────────────────┴──────────────────────────────────┤
│ [下] Agent Trace (4 個 agent 的對話過程)                 │
│ 🤖 order_intake: [W1 stub] returned canned spec...     │
│ 🤖 capacity: 1000 × 2U × 1.2h = 1200h; threshold 5000h │
│ 🤖 pricing: similar to HIST-001, 92% match...          │
│ 🤖 esg: 1000 × 2U × 120kg = 120000kg                   │
└─────────────────────────────────────────────────────────┘
```

Streamlit 內建的 `st.chat_message`、`st.metric`、`st.dataframe` 都好用。

#### 2. 學 Streamlit 的進階功能

W1 plan 的 Streamlit 程式碼是**最小可跑版本**。Demo 要漂亮，你要加：

- **`st.status` / `st.spinner`**：agent 跑的時候顯示進度
- **`st.chat_message(name)`**：每個 agent 用不同 avatar
- **`st.expander`**：「點開看詳細推理」
- **`st.tabs`**：可以切換 demo 情境
- **CSS 微調**：透過 `st.markdown(..., unsafe_allow_html=True)`，重點數字放大、加色

教學資源：
- https://docs.streamlit.io/library/api-reference/chat
- https://docs.streamlit.io/library/api-reference/data
- https://streamlit.io/gallery（找 chatbot 類別的範例偷學）

#### 3. 準備 3 個 Demo 情境的輸入文字

跟團隊一起想：

| # | 情境 | 客戶需求文字（demo 時直接點預設按鈕填入） |
|---|---|---|
| 1 | 正常單 | `"AWS Q3 訂單：1000 台 2U 機型，Xeon-9654、512GB RAM、20TB NVMe，8 月底前交貨"` |
| 2 | 急單 | `"Meta 緊急加單：兩週內需要 5000 台 1U Xeon-8480 256GB，產線可能要外援"` |
| 3 | 規格變更 | `"原 Google 訂單 #G-2024-093：CPU 從 EPYC-9554 換成 9654，數量不變，重新報價並評估碳排影響"` |

UI 上做成「Demo 情境」下拉選單，按一下自動填入。

#### 4. 跟團隊敲定字型 / 配色 / Logo

- 字型：用系統預設 / Google Fonts？
- 主色：綠色（ESG 主題）or 藍色（科技感）or 兩者？
- Logo：要不要做一個？（簡單的 emoji 也行：🌱🤖）

## Task 9: Streamlit Scaffold（5/23 起）

Agent 組推完 Task 6，你 pull 下來：

```bash
git pull
source .venv/bin/activate
streamlit run ui/streamlit_app.py
```

照 [plan Task 9](../superpowers/plans/2026-05-18-w1-scaffold.md#task-9-streamlit-ui-scaffold) 的 minimum 版本先跑起來，再做美化。

## W2 / W3 要做的事

### W2（5/25 – 5/31）
- 接 real LLM（agents 不再回 stub）的 streaming agent trace
- Prompt debug 面板（給隊友調 prompt 用）
- 至少 1 個情境 end-to-end demo 可看

### W3（6/1 – 6/7）—— **這週是你的主場**
- 3 個情境的 demo 流程順
- 加動畫 / 配色 / 統計指標
- 錄 demo video（plan B）
- 上 demo 簡報投影片（跟 PM 合作）

## 規則

1. **不要在 Streamlit 程式碼裡叫 `litellm` 或 LLM API**——一律 `run_orchestrator()`
2. **不要在 UI 寫業務邏輯**——所有計算在 orchestrator / agents
3. **不要把 `.env` 內容 hardcode 進 UI**——`os.getenv()` 就好
4. **不要改 `shared/models.py`**——UI 只讀 schema、不改 schema

## 你可能踩的雷

| 雷 | 怎麼避 |
|---|---|
| Streamlit 預設每次按鈕都 rerun 整頁 | 用 `st.session_state` 儲存中間狀態 |
| Agent trace 沒 streaming，UI 等很久才出結果 | W2 用 `st.write_stream()` 或 placeholder 邊跑邊更新 |
| Demo 當天 LLM API 出包 | 錄 video 當 plan B；或寫一個「fake mode」用預錄結果 |
| 字太多看起來醜 | 重點數字用 `st.metric`，細節塞 `st.expander` |
| Layout 在小螢幕跑掉 | Demo 前一天用會議室那台投影機實測 |

## W1 驗收

- [ ] UI 草圖跟團隊敲定
- [ ] 3 個 demo 情境文字寫好（放在 `docs/team/demo_scenarios.md` 或本檔尾）
- [ ] Streamlit 雛形跑得起來（等 Agent 組 Task 6 後完成 Task 9）
- [ ] 點按鈕能看到 4 個 agent 的訊息 + 協調報告卡片

## 連結

- Plan 細節：[`docs/superpowers/plans/2026-05-18-w1-scaffold.md`](../superpowers/plans/2026-05-18-w1-scaffold.md)（Task 9）
- 系統設計：[`docs/superpowers/specs/2026-05-18-multi-agent-design.md`](../superpowers/specs/2026-05-18-multi-agent-design.md)
- Schemas 你會用到的：[`shared/models.py`](../../shared/models.py)
