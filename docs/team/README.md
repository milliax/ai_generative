# 團隊分工文件

每個人**請優先讀自己的那份**，再瀏覽其他組的——這樣你知道別人在做什麼、什麼時候會 unblock 你。

| 角色 | 人數 | 文件 |
|---|---|---|
| PM / 統整 | 1 | [pm.md](pm.md) |
| Agent 編排 | 2 | [agents.md](agents.md) |
| 估價 / RAG | 2 | [pricing.md](pricing.md) |
| UI / Demo | 1 | [ui.md](ui.md) |

## 你第一次來這個 repo 該做什麼

1. 看 [`README.md`](../../README.md)（10 分鐘）瞭解專案要做什麼
2. 看 [`CLAUDE.md`](../../CLAUDE.md)（5 分鐘）瞭解工作規則
3. 看 **你那組的文件**（10 分鐘）瞭解自己要做什麼
4. 看 [`docs/superpowers/specs/2026-05-18-multi-agent-design.md`](../superpowers/specs/2026-05-18-multi-agent-design.md)（20 分鐘）瞭解整個系統設計
5. 看 [`docs/superpowers/plans/2026-05-18-w1-scaffold.md`](../superpowers/plans/2026-05-18-w1-scaffold.md) 中**屬於你的 task**（30 分鐘）瞭解具體要寫什麼

跑起來：

```bash
git clone git@github.com:milliax/ai_generative.git
cd ai_generative
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env，填入你的 LLM provider key（Gemini Flash 免費版最快）
pytest                          # 應該 14 passing
```

跑得起來、測試全綠，你就準備好開工了。

## 依賴關係速查

```
PM 已交付（shared/models.py、shared/llm_client.py）
        ↓
    Agent 組 (Task 4: BaseAgent → Task 5: 4 specialists → Task 6: orchestrator)
        ↓
    UI 組 (Task 9: Streamlit)

PM 已交付
        ↓
    估價組 (Task 7: mock data → Task 8: RAG)
        ↓ (W2 才接)
    Agent 組的 PricingAgent

PM 自己 (Task 10: e2e test)
    ← 等 Agent 組 + 估價組都完成
```

## 群組溝通約定

- **改 `shared/models.py`**：必須群組討論，PM 把關
- **改 `shared/llm_client.py`**：同上
- **加新 dependencies 到 `requirements.txt`**：群組通知
- **每天 push 前**：先 `git pull` + `pytest` + `ruff check .`
- **Push 把 main 弄壞**：立刻通報，不要默默修
