from __future__ import annotations

from typing import Any

from shared.models import AgentMessage
from .base import BaseAgent

SYSTEM_PROMPT = """你是電線電纜廠的資深業務報價專家（Palantir 風格：估價必須 show your work）。
你會收到一筆新訂單規格，以及從歷史資料庫找到的最相似歷史案例（含 similarity 分數）。

請根據參考案例推算報價與交期，輸出繁體中文條列式依據。
若歷史案例 similarity 低於 0.6，請說明「參考案例相似度偏低，建議人工複核」。"""


def _format_rag_results(records: list[dict[str, Any]]) -> str:
    lines = []
    for i, r in enumerate(records, 1):
        lines.append(
            f"【案例{i}】order_id={r.get('order_id', 'N/A')} "
            f"similarity={r.get('similarity', 0):.2f}\n"
            f"  摘要：{r.get('matched_summary', '')}\n"
            f"  建議處置：{r.get('recommended_action', 'N/A')}  "
            f"綜合風險：{r.get('overall_risk_score', 'N/A')}  "
            f"預估延誤：{r.get('estimated_delay_days', 'N/A')}天"
        )
    return "\n".join(lines)


class PricingAgent(BaseAgent):
    name = "pricing"
    system_prompt = SYSTEM_PROMPT

    def run(self, payload: dict[str, Any]) -> AgentMessage:
        spec = payload.get("spec", {})
        rag_records = payload.get("rag_records", [])  # 由 orchestrator 傳入

        if not rag_records:
            # fallback：RAG 沒有結果就用 stub 公式
            memory_gb = int(spec.get("memory_gb", 64))
            quantity = int(spec.get("quantity", 1))
            estimated_price = float(memory_gb * quantity * 100)
            reasoning = "[FALLBACK] RAG 無結果，使用 stub 公式估價。"
            reference_orders = []
        else:
            # 有 RAG 結果：呼叫 LLM 推理
            user_prompt = f"""
【新訂單規格】: {spec}

【歷史相似案例】:
{_format_rag_results(rag_records)}

請輸出：
1. 建議單價（NTD/噸）
2. 建議交期（天數）
3. 估價信心分數（1-100）
4. 條列式估價依據
5. 參考訂單編號（最多3筆）
"""
            llm_response = self.call_llm_text(user_prompt)
            estimated_price = 0.0  # LLM 自由文字，price 從 reasoning 讀
            reasoning = llm_response
            reference_orders = [
                {"order_id": r.get("order_id", ""), "similarity": r.get("similarity", 0)}
                for r in rag_records[:3]
            ]

        return AgentMessage(
            from_agent=self.name,
            to_agent=None,
            payload={
                "estimated_price": estimated_price,
                "reference_orders": reference_orders,
            },
            reasoning=reasoning,
        )