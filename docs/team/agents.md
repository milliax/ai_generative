# Agent 編排組 工作指南

> 2 人。負責 LangGraph orchestrator + 4 個 specialist agents。

## 你們的定位

你們做的是**整個系統的大腦**——當客戶單進來，要決定呼叫哪些 agents、用什麼順序、怎麼整合結果。這也是 demo 時最有故事性的部分（「看，agents 自己討論出協調方案」）。

## 你們可以依賴的東西（PM 已交付）

```python
from shared.models import OrderRequest, OrderSpec, AgentMessage, CoordinationPlan
from shared.llm_client import call_llm, LLMError
```

- `shared/models.py` —— **不准改**，要改先群組討論
- `shared/llm_client.py` —— 你們呼叫 LLM 的**唯一**入口

## 分工建議

| 人 | Task | 檔案 |
|---|---|---|
| **A** | Task 4: BaseAgent + Task 5a: Order Intake + Task 5b: Capacity | `agents/base.py`、`agents/order_intake.py`、`agents/capacity.py` |
| **B** | Task 5c: Pricing + Task 5d: ESG + Task 6: Orchestrator | `agents/pricing.py`、`agents/esg.py`、`agents/orchestrator.py` |

依賴關係：**A 的 BaseAgent（Task 4）一定要先做完**，B 才能開始 specialist agents。建議 A 第一天就把 Task 4 推上去。

## W1 策略：「Stub + 真實 prompt」

**這週所有 agents 不真的呼叫 LLM**——每個 `run()` 都回 canned response，但 prompt 結構（`PROMPT = """..."""`）保留好。W2 時把 mock 拔掉、接 `call_llm()` 即可。

理由：
1. 不燒 API token（debug 時跑很多次）
2. 測試不依賴外部 API
3. 你們可以先把 agent 間的訊息流程跑通

完整 stub 程式碼範例在 [`docs/superpowers/plans/2026-05-18-w1-scaffold.md#task-5`](../superpowers/plans/2026-05-18-w1-scaffold.md)。

## 你們要做的 task（TDD 流程）

每個 task 跑：
1. 先寫測試（測試該 fail）
2. 跑 `pytest tests/test_<thing>.py -v` 確認 fail
3. 寫實作讓測試 pass
4. 跑 `pytest` 確認 pass
5. `git commit` 並 push

### Task 4: BaseAgent（A 做，**Day 1 必達**）

```python
# agents/base.py
from abc import ABC, abstractmethod
from shared.llm_client import call_llm
from shared.models import AgentMessage

class BaseAgent(ABC):
    name: str = ""
    system_prompt: str = ""

    def call_llm_text(self, user_prompt: str, **kwargs) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return call_llm(messages, **kwargs)

    @abstractmethod
    def run(self, payload: dict) -> AgentMessage:
        raise NotImplementedError
```

完整測試在 plan。

### Task 5: 4 個 Specialist Agents（A/B 並行）

每個 agent 都繼承 `BaseAgent`，在 W1 回 canned response：

- **Order Intake**：解析客戶需求 → 結構化 spec。W1 stub: 回固定假規格
- **Capacity**：查 IoT 估產能。W1 stub: `quantity × hours_per_chassis`，過 5000h 算 overload
- **Pricing**：RAG 估價。W1 stub: `memory_gb × quantity × 100` + 3 筆假參考訂單
- **ESG**：碳排 + 替代供應商。W1 stub: `quantity × kg_per_chassis` + 2 個假供應商

每個 agent 都要有 `PROMPT` 常數（W2 才會真的用）。

### Task 6: LangGraph Orchestrator（B 做）

```
START → intake → capacity → pricing → esg → END
                     ↓         ↓        ↓
                  state 累積 + aggregator → CoordinationPlan
```

完整實作在 plan。注意：

- State 是 `TypedDict`，包含 `request, spec, capacity_result, pricing_result, esg_result, trace`
- `trace: list[AgentMessage]` 給 UI 顯示用
- 最後的 `_aggregate()` 函式把所有 agent 結果組成 `CoordinationPlan`

## 規則（不准違反）

1. **不要 `import litellm`**——一律走 `call_llm()`
2. **不要改 `shared/models.py`**——有需求先群組討論
3. **每個 agent 都要繼承 `BaseAgent`**——統一介面，方便 orchestrator 串
4. **每個 agent 回 `AgentMessage`**——其中 `reasoning` 欄位非空（給 UI 顯示）
5. **PROMPT 寫成 module 常數**——`PROMPT = """..."""`，方便 code review
6. **每個 agent 都要有測試**——至少測 `run()` 回正確型別的 message

## 給 prompt 設計的提醒

W1 雖然不真的用，但 prompt 結構要寫得**像真的**，因為 W2 直接會用：

- System prompt：定義 agent 的「角色」
- User prompt：把輸入結構化（用 f-string 或 jinja，不要 string concat）
- 要 LLM 回 JSON：明確列出所有鍵跟型別
- 給 examples（few-shot）：W2 prompt 調校時會用到

## 你們可能踩的雷

| 雷 | 怎麼避 |
|---|---|
| Agent 之間直接傳 dict | 全部用 `AgentMessage` 包起來 |
| 在 agent 裡寫死 model 名稱 | 一律走 `call_llm()`（會讀 env） |
| LangGraph state 改成 mutable 結構 | 用 `TypedDict`，state 是不可變的 view |
| Aggregator 邏輯塞進某個 agent | 分開——agents 只做專業判斷，組合在 orchestrator 的 `_aggregate()` |
| Stub response 跟 schema 不合 | 寫完 stub 立刻跑測試 |

## W1 驗收

- [ ] `pytest -v` 全綠（增加 ~10 個 tests）
- [ ] `python -c "from agents.orchestrator import run_orchestrator; ..."` 能跑出 CoordinationPlan
- [ ] Trace 包含 4 個 agent 的訊息，順序正確

## 連結

- 完整 task 內容：[`docs/superpowers/plans/2026-05-18-w1-scaffold.md`](../superpowers/plans/2026-05-18-w1-scaffold.md)
- 系統設計：[`docs/superpowers/specs/2026-05-18-multi-agent-design.md`](../superpowers/specs/2026-05-18-multi-agent-design.md)
- Schemas：[`shared/models.py`](../../shared/models.py)
- LLM client：[`shared/llm_client.py`](../../shared/llm_client.py)
