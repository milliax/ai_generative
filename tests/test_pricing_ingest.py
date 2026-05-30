from __future__ import annotations

from pathlib import Path

import chromadb
import pandas as pd
import pytest

from pricing.ingest import (
    COLLECTION_NAME,
    build_metadata_records,
    ingest_orders_to_chroma,
)


def write_orders_csv(csv_path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")


def build_valid_rows() -> list[dict]:
    return [
        {
            "order_id": "ORD2026-00001",
            "spec_summary": "客戶=A；產品族群=CV；需求數量=1.5噸；綜合風險=58.1",
            "customer": "測試客戶A",
            "product_family": "CV",
            "overall_risk_score": 58.1,
            "estimated_delay_days": 0.7,
            "recommended_action": "正常排程但需觀察",
        },
        {
            "order_id": "ORD2026-00002",
            "spec_summary": "客戶=B；產品族群=IV；需求數量=0.5噸；綜合風險=42.0",
            "customer": "測試客戶B",
            "product_family": "IV",
            "overall_risk_score": 42.0,
            "estimated_delay_days": 0.0,
            "recommended_action": "可依一般規則排程",
        },
    ]


def test_ingest_orders_to_chroma_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = tmp_path / "teacher_orders_for_rag.csv"
    persist_dir = tmp_path / "chroma_db"
    write_orders_csv(csv_path, build_valid_rows())

    def fake_embed_documents(documents: list[str]) -> list[list[float]]:
        return [[float(index), 0.0, 1.0] for index, _ in enumerate(documents)]

    monkeypatch.setattr("pricing.ingest.embed_documents", fake_embed_documents)

    ingested_count = ingest_orders_to_chroma(
        csv_path=csv_path,
        persist_dir=persist_dir,
    )

    assert ingested_count == 2

    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_collection(COLLECTION_NAME)

    assert collection.count() == 2

    stored = collection.get(
        ids=["ORD2026-00001"],
        include=["documents", "metadatas"],
    )

    assert stored["documents"] == ["客戶=A；產品族群=CV；需求數量=1.5噸；綜合風險=58.1"]
    assert stored["metadatas"][0]["customer"] == "測試客戶A"
    assert stored["metadatas"][0]["product_family"] == "CV"
    assert stored["metadatas"][0]["overall_risk_score"] == 58.1


def test_ingest_orders_to_chroma_missing_spec_summary_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "teacher_orders_for_rag.csv"
    rows = build_valid_rows()

    for row in rows:
        row.pop("spec_summary")

    write_orders_csv(csv_path, rows)

    with pytest.raises(ValueError, match="missing required columns"):
        ingest_orders_to_chroma(csv_path=csv_path, persist_dir=tmp_path / "chroma_db")


def test_ingest_orders_to_chroma_duplicate_order_id_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "teacher_orders_for_rag.csv"
    rows = build_valid_rows()
    rows[1]["order_id"] = rows[0]["order_id"]

    write_orders_csv(csv_path, rows)

    with pytest.raises(ValueError, match="duplicated values"):
        ingest_orders_to_chroma(csv_path=csv_path, persist_dir=tmp_path / "chroma_db")


def test_ingest_orders_to_chroma_empty_spec_summary_raises(tmp_path: Path) -> None:
    csv_path = tmp_path / "teacher_orders_for_rag.csv"
    rows = build_valid_rows()
    rows[0]["spec_summary"] = "   "

    write_orders_csv(csv_path, rows)

    with pytest.raises(ValueError, match="empty documents"):
        ingest_orders_to_chroma(csv_path=csv_path, persist_dir=tmp_path / "chroma_db")


def test_build_metadata_records_sanitizes_missing_values() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "order_id": "ORD2026-00001",
                "spec_summary": "測試摘要",
                "customer": "測試客戶A",
                "optional_note": pd.NA,
            }
        ]
    )

    metadata_records = build_metadata_records(dataframe)

    assert metadata_records == [
        {
            "order_id": "ORD2026-00001",
            "customer": "測試客戶A",
            "optional_note": "",
        }
    ]
