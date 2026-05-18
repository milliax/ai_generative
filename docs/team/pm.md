# PM / 統整 工作指南

> 1 人。負責整合、品質把關、demo。

## 你的定位

你是團隊的「合約守門員」與「demo 主導者」。**不寫 agent、不寫 RAG、不寫 UI**——你的價值是讓另外 5 個人寫的東西能整合在一起、跑得起來、能 demo。

## 你已經交付的（W1 第一波）

| 檔案 | 狀態 |
|---|---|
| `pyproject.toml`、`requirements.txt`、`.env.example` | ✅ 已 push |
| `shared/models.py`（4 個 Pydantic schemas）| ✅ 14/14 tests pass |
| `shared/llm_client.py`（LiteLLM wrapper） | ✅ 4/4 tests pass |

其他人現在已經可以開工。

## W1 剩下要做的事（5/19 – 5/24）

### 1. 每天的固定動作

```bash
git pull
source .venv/bin/activate
pytest                          # 確保 main 全綠
ruff check .                    # 確保沒有 lint warning
```

如果有人 push 把 main 弄壞了，**立刻**在群組 ping 那個人。不要默默修。

### 2. Code review

W1 每個 PR / commit 你都要看一眼，特別檢查：

- [ ] **有沒有人繞過 `shared/llm_client.py`？** Grep：`grep -rn "import litellm\|from litellm" agents/ pricing/ ui/`——除了 `shared/llm_client.py` 外不該有任何結果
- [ ] **有沒有人改 `shared/models.py`？** 任何改動都要團隊討論，不能單人直接 push
- [ ] **新加的 agent 是不是回 `AgentMessage`？** 不是的話打回去重做
- [ ] **測試有沒有跟著加？** 每個新檔案都要有對應 test

### 3. Task 10：End-to-end smoke test

當 Task 6（orchestrator）完成後，你寫 `tests/test_e2e.py`，這是 **W1 完成的驗收標準**。完整內容在 [`docs/superpowers/plans/2026-05-18-w1-scaffold.md`](../superpowers/plans/2026-05-18-w1-scaffold.md#task-10-end-to-end-smoke-test)。

### 4. 跟老師確認資料（**最緊急**）

W1 plan 的未解問題：
- 老師會給什麼欄位？格式？什麼時候會給？
- 系上有沒有 OpenAI / GCP credit 可以申請？

**5/20 前一定要敲到老師**——估價組要等資料才能做有意義的工作。

### 5. 邀請隊友當 GitHub collaborator

到 https://github.com/milliax/ai_generative/settings/access 把 5 個隊友加進來。

## W2 要做的事（5/25 – 5/31）

- **5/24 前寫 W2 plan**：路徑 `docs/superpowers/plans/2026-05-25-w2-real-llm-and-rag.md`
- 範圍：拿掉 agents 的 canned response 換真 LLM、RAG 從 stub 換成真實估價、UI 加 streaming
- 找 Claude 用 `superpowers:writing-plans` skill 來寫

## W3 要做的事（6/1 – 6/7）

- 寫 demo 簡報（投影片）
- 排 3 個 demo 情境腳本（正常單 / 急單 / 規格變更）
- 錄一份 demo video 當 plan B（萬一 demo 當天 LLM API 出包）
- 統整最終整合測試

## 你絕對不能放手的東西

| 守則 | 為什麼 |
|---|---|
| **`shared/models.py` 不准單人改** | 改動會影響整個團隊。要改先在群組討論。 |
| **`shared/llm_client.py` 只走這一個入口** | Provider 切換、cost tracking 都靠這個。 |
| **`.env` 永遠不能 commit** | `.gitignore` 已經擋了，但 review 時再多看一眼。 |
| **`data/` 不准 commit** | 老師資料可能有 NDA、且 repo 會肥大。`.gitignore` 也擋了。 |
| **Branch 策略** | 目前直接 push main。W2 之後如果衝突變多，可以改 PR 流程。 |

## 你可能會被問到的問題（QA 備忘）

- **「我可以加一個欄位到 `OrderSpec` 嗎？」** → 先在群組討論。如果同意，你來改，所有人 pull 一下。
- **「`call_llm()` 的 retry 次數可以調嗎？」** → 可以，呼叫時傳 `max_retries=N`。不要改預設。
- **「我可以用 ChatGPT 訂閱嗎？」** → 不行。看 [`README.md` 第三節](../../README.md#三技術選型)。要用 OpenAI 必須去 https://platform.openai.com/ 開帳號儲值。建議用 Gemini Flash 免費版。
- **「測試很慢怎麼辦？」** → 看是不是有人忘記 monkeypatch `time.sleep`，或忘記 mock LLM 呼叫。

## 連結

- 完整 spec：[`docs/superpowers/specs/2026-05-18-multi-agent-design.md`](../superpowers/specs/2026-05-18-multi-agent-design.md)
- W1 plan：[`docs/superpowers/plans/2026-05-18-w1-scaffold.md`](../superpowers/plans/2026-05-18-w1-scaffold.md)
- 討論記錄：[`docs/discussions/`](../discussions/)
- 工作規則：[`CLAUDE.md`](../../CLAUDE.md)
