from __future__ import annotations

from datetime import date, datetime, timedelta
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


def _build_fallback_payload(
    spec: dict[str, Any],
    rag_records: list[dict[str, Any]],
    warning: str | None = None,
) -> dict[str, Any]:
    quantity_ton = float(spec.get("quantity_ton", 1.0))
    estimated_price = round(quantity_ton * 85000, 2)
    low = round(estimated_price * 0.95, 2)
    high = round(estimated_price * 1.05, 2)

    requested_delivery = spec.get("requested_delivery")
    if isinstance(requested_delivery, datetime):
        estimated_delivery = requested_delivery.date().isoformat()
    elif isinstance(requested_delivery, date):
        estimated_delivery = requested_delivery.isoformat()
    elif isinstance(requested_delivery, str) and requested_delivery:
        estimated_delivery = requested_delivery
    else:
        estimated_delivery = (date.today() + timedelta(days=30)).isoformat()

    result: dict[str, Any] = {
        "estimated_price": estimated_price,
        "price_confidence": [low, high],
        "estimated_delivery": estimated_delivery,
        "reference_orders": [dict(record) for record in rag_records[:3]],
        "pricing_mode": "fallback",
    }
    if warning:
        result["warning"] = warning

    return result


class PricingAgent(BaseAgent):
    name = "pricing"
    system_prompt = SYSTEM_PROMPT

    def run(self, payload: dict[str, Any]) -> AgentMessage:
        spec = payload.get("spec", {})
        rag_records = payload.get("rag_records", [])

        if not rag_records:
            result_payload = _build_fallback_payload(
                spec,
                rag_records=[],
                warning="RAG retrieval returned no records.",
            )
            reasoning = "[FALLBACK] RAG 無結果，使用電纜噸數 stub 公式估價。"
            return AgentMessage(
                from_agent=self.name,
                to_agent=None,
                payload=result_payload,
                reasoning=reasoning,
            )

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
        result_payload = _build_fallback_payload(spec, rag_records)

        try:
            llm_response = self.call_llm_text(user_prompt)
            result_payload["pricing_mode"] = "rag_llm"
            result_payload["llm_analysis"] = llm_response
            reasoning = llm_response
        except Exception as exc:  # noqa: BLE001
            result_payload["warning"] = (
                "LLM pricing analysis failed; returned RAG references with fallback formula. "
                f"Reason: {exc}"
            )
            reasoning = result_payload["warning"]

        return AgentMessage(
            from_agent=self.name,
            to_agent=None,
            payload=result_payload,
            reasoning=reasoning,
        )
