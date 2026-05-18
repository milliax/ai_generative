# 討論記錄：W1 PM Blocker Tasks 執行

**日期：** 2026-05-19
**參與者：** Max（+ Claude，subagent-driven execution）
**主題：** 執行 W1 plan 的 Task 1-3（PM 必交付項目），unblock 其他隊員

## 完成項目

PM 三個 blocker tasks 全部完成、測試通過、推上 GitHub。

| Task | 交付 | Commits | 測試 |
|---|---|---|---|
| 1. Repo skeleton | `pyproject.toml`、`requirements.txt`、`.env.example`、6 個 `__init__.py` | `fc30149` | — |
| 2. Pydantic schemas | `shared/models.py`（4 個 models）、`tests/test_models.py` | `3c47e59` + `3840afd`（review fix） | 9/9 |
| 3. LiteLLM wrapper | `shared/llm_client.py`、`tests/test_llm_client.py` | `cf4e90f` + `69325a9`（review fix） | 4/4 |

**全部測試：** 13/13 passing
**Push：** `origin/main` at `69325a9`

## Code Review 發現與修正

### Task 2 (Pydantic schemas) 補丁

Reviewer 找到 3 個 stable interface 上的真實 bug：

1. `cpu_sku: str` 允許空字串 → 加 `Field(min_length=1)`
2. `AgentMessage.reasoning: str` 允許空字串（破壞稽核性）→ 加 `Field(min_length=1)`
3. `CoordinationPlan.price_confidence: tuple[float, float]` 不檢查 `low <= high` → 加 `@model_validator`

並補 4 個 rejection tests（驗證 `memory_gb=0`、`quantity=0`、空 `cpu_sku`、反轉 confidence 都被拒）。

### Task 3 (LLM client) 補丁

1. log 訊息把 `len(content)`（字元數）當 token 數 → 改用 `resp.usage.completion_tokens`
2. retry warning 沒記 exception type，debug 困難 → 加 `type(e).__name__`

### 被刻意跳過的建議（避免 bikeshed）

- `capacity_status: str` 改 `Literal` — 寫死太早，留給之後 W2 決定
- `alternative_suppliers`/`reference_orders` 改 TypedDict — 課程專題用不到這層嚴謹
- docstring 中英文混用 — 不影響功能

## 隊員現在可以做的事

`git pull` 拉下來後：

```bash
cp .env.example .env          # 填自己的 LLM provider key
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest                         # 應該 13 passing
```

接著各組可以開始：

| 組 | 起手 task | 路徑 |
|---|---|---|
| Agent 編排（2 人） | Task 4: BaseAgent class | `agents/base.py` |
| 估價 / RAG（2 人） | Task 7: Mock data generator | `scripts/generate_mock_orders.py` |
| UI（1 人） | 暫時無事 — 等 Task 6 (orchestrator) 完成才能接 | 可先設計 UI mockup |

`shared/models.py` 跟 `shared/llm_client.py` 是 stable，請各組**不要直接修改**，有需求先到 issue / 群組討論。

## 流程觀察

- **Subagent-driven execution** 走 TDD + 兩階段 review（spec compliance + code quality），找到 5 個非顯然的 bug（empty string 驗證、price ordering、misleading log）
- 純 scaffold task（Task 1）跳過 code quality review，省時間
- 用 haiku 跑 mechanical task（scaffold、spec review）、sonnet 跑有判斷的 task（schemas、LLM client、code quality review）

## 待辦

- [ ] 邀請 5 個隊友加 GitHub repo collaborator（給 Max usernames）
- [ ] 找老師確認資料欄位（W1 plan Section 8 未解問題）
- [ ] Agent 組可開始 Task 4-6
- [ ] 估價組可開始 Task 7-8
- [ ] 寫 W2 plan（5/24 前）

## 對 README / Spec 的影響

無——README 跟 spec 在這次執行中沒有需要修改的內容。所有資訊都涵蓋在 `docs/superpowers/plans/2026-05-18-w1-scaffold.md`。
