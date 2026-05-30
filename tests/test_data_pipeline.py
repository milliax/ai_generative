from pathlib import Path

import pytest

from shared import data_pipeline


def test_find_raw_excel_none_when_empty(tmp_path):
    assert data_pipeline.find_raw_excel(tmp_path) is None


def test_find_raw_excel_returns_first_xlsx(tmp_path):
    (tmp_path / "teacher.xlsx").write_bytes(b"x")
    assert data_pipeline.find_raw_excel(tmp_path) == tmp_path / "teacher.xlsx"


def test_data_status_all_missing(tmp_path):
    status = data_pipeline.data_status(
        raw_dir=tmp_path / "raw",
        db_path=tmp_path / "x.db",
        csv_path=tmp_path / "x.csv",
        persist_dir=tmp_path / "chroma",
    )
    assert status.db_ready is False
    assert status.csv_ready is False
    assert status.chroma_ready is False
    assert status.raw_excel_path is None


def test_data_status_detects_db_and_csv(tmp_path):
    import sqlite3

    db = tmp_path / "x.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE orders (a)")
    conn.execute("INSERT INTO orders VALUES (1)")
    conn.commit()
    conn.close()
    csv = tmp_path / "x.csv"
    csv.write_text("order_id,spec_summary\nO1,hello\n")

    status = data_pipeline.data_status(
        raw_dir=tmp_path,
        db_path=db,
        csv_path=csv,
        persist_dir=tmp_path / "chroma",
    )
    assert status.db_ready is True
    assert status.csv_ready is True
    assert status.csv_rows == 1


def test_run_full_pipeline_calls_steps_in_order(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(data_pipeline, "build_database", lambda *a, **k: calls.append("db") or {"orders": 2})
    monkeypatch.setattr(data_pipeline, "convert_for_rag", lambda *a, **k: calls.append("csv") or 3)
    monkeypatch.setattr(data_pipeline, "ingest_to_chroma", lambda *a, **k: calls.append("chroma") or 3)

    events = []
    data_pipeline.run_full_pipeline(
        excel_path=tmp_path / "in.xlsx",
        progress_callback=lambda step, status, detail: events.append((step, status)),
    )
    assert calls == ["db", "csv", "chroma"]
    assert ("build_db", "done") in events


def test_run_full_pipeline_stops_on_failure(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(data_pipeline, "build_database", lambda *a, **k: calls.append("db") or {"orders": 2})

    def boom(*a, **k):
        raise RuntimeError("convert failed")

    monkeypatch.setattr(data_pipeline, "convert_for_rag", boom)
    monkeypatch.setattr(data_pipeline, "ingest_to_chroma", lambda *a, **k: calls.append("chroma"))

    with pytest.raises(RuntimeError, match="convert failed"):
        data_pipeline.run_full_pipeline(excel_path=tmp_path / "in.xlsx", progress_callback=lambda *a: None)
    assert "chroma" not in calls


def test_data_status_csv_with_bom_counts_correctly(tmp_path):
    csv = tmp_path / "bom.csv"
    csv.write_text("﻿order_id,spec_summary\nO1,hello\nO2,world\n", encoding="utf-8")
    status = data_pipeline.data_status(
        raw_dir=tmp_path,
        db_path=tmp_path / "x.db",
        csv_path=csv,
        persist_dir=tmp_path / "chroma",
    )
    assert status.csv_rows == 2
