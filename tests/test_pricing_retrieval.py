from __future__ import annotations

from typing import Any

import pytest

from pricing.retrieval import (
    build_retrieval_result,
    retrieve_similar,
)


class FakeCollection:
    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str],
    ) -> dict[str, list[list[Any]]]:
        assert query_embeddings == [[0.1, 0.2, 0.3]]
        assert n_results == 2
        assert include == ["documents", "metadatas", "distances"]

        return {
            "documents": [
                [
                    "客戶=A；產品族群=CV；綜合風險=58.1",
                    "客戶=B；產品族群=IV；綜合風險=42.0",
                ]
            ],
            "metadatas": [
                [
                    {
                        "order_id": "ORD2026-00001",
                        "customer": "測試客戶A",
                        "product_family": "CV",
                        "overall_risk_score": 58.1,
                    },
                    {
                        "order_id": "ORD2026-00002",
                        "customer": "測試客戶B",
                        "product_family": "IV",
                        "overall_risk_score": 42.0,
                    },
                ]
            ],
            "distances": [[0.15, 0.35]],
        }


def test_retrieve_similar_returns_metadata_summary_and_similarity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pricing.retrieval.embed_query", lambda query: [0.1, 0.2, 0.3])
    monkeypatch.setattr("pricing.retrieval.get_collection", lambda **kwargs: FakeCollection())

    results = retrieve_similar(
        query="急單 CV 電纜 需求數量 1.5 噸",
        k=2,
        persist_dir="unused",
    )

    assert len(results) == 2

    assert results[0]["order_id"] == "ORD2026-00001"
    assert results[0]["customer"] == "測試客戶A"
    assert results[0]["product_family"] == "CV"
    assert results[0]["matched_summary"] == "客戶=A；產品族群=CV；綜合風險=58.1"
    assert results[0]["similarity"] == 0.85

    assert results[1]["order_id"] == "ORD2026-00002"
    assert results[1]["similarity"] == 0.65


def test_retrieve_similar_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        retrieve_similar("   ")


def test_retrieve_similar_rejects_invalid_k() -> None:
    with pytest.raises(ValueError, match="k must be greater than or equal to 1"):
        retrieve_similar("valid query", k=0)


def test_build_retrieval_result_clamps_similarity() -> None:
    too_small = build_retrieval_result(
        document="測試摘要",
        metadata={"order_id": "A"},
        distance=1.5,
    )
    too_large = build_retrieval_result(
        document="測試摘要",
        metadata={"order_id": "B"},
        distance=-0.5,
    )

    assert too_small["similarity"] == 0.0
    assert too_large["similarity"] == 1.0
