"""Data onboarding pipeline: detect status and convert the teacher xlsx into
both a SQLite DB (for Capacity/ESG SQL) and a ChromaDB index (for Pricing RAG).

Pure functions, no Streamlit import. This is the only interface the UI uses.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pricing.ingest import COLLECTION_NAME, get_persist_dir, ingest_orders_to_chroma
from scripts.build_db import DEFAULT_DB_PATH, build_database
from scripts.convert_teacher_excel import convert_teacher_excel

DEFAULT_RAW_DIR = Path("raw_data")
DEFAULT_CSV_PATH = Path("data/teacher_orders_for_rag.csv")

# progress_callback signature: (step: str, status: str, detail: str) -> None
ProgressCallback = Callable[[str, str, str], None]


@dataclass
class DataStatus:
    db_ready: bool
    csv_ready: bool
    chroma_ready: bool
    db_tables: int
    csv_rows: int
    chroma_count: int
    raw_excel_path: Path | None


def find_raw_excel(raw_dir: str | Path = DEFAULT_RAW_DIR) -> Path | None:
    """Return the first *.xlsx in raw_dir, or None."""
    raw_dir = Path(raw_dir)
    if not raw_dir.exists():
        return None
    matches = sorted(raw_dir.glob("*.xlsx"))
    return matches[0] if matches else None


def _db_table_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()
        return int(rows[0]) if rows else 0
    finally:
        conn.close()


def _csv_row_count(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    with csv_path.open(encoding="utf-8-sig") as handle:
        return max(sum(1 for _ in handle) - 1, 0)  # minus header


def _chroma_count(persist_dir: str | Path | None) -> int:
    try:
        import chromadb

        client = chromadb.PersistentClient(path=get_persist_dir(persist_dir))
        return client.get_collection(COLLECTION_NAME).count()
    except Exception:
        return 0


def data_status(
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    db_path: str | Path = DEFAULT_DB_PATH,
    csv_path: str | Path = DEFAULT_CSV_PATH,
    persist_dir: str | Path | None = None,
) -> DataStatus:
    db_path = Path(db_path)
    csv_path = Path(csv_path)
    db_tables = _db_table_count(db_path)
    csv_rows = _csv_row_count(csv_path)
    chroma_count = _chroma_count(persist_dir)
    return DataStatus(
        db_ready=db_tables > 0,
        csv_ready=csv_rows > 0,
        chroma_ready=chroma_count > 0,
        db_tables=db_tables,
        csv_rows=csv_rows,
        chroma_count=chroma_count,
        raw_excel_path=find_raw_excel(raw_dir),
    )


def convert_for_rag(excel_path: str | Path, csv_path: str | Path = DEFAULT_CSV_PATH) -> int:
    """Convert xlsx -> RAG CSV using the existing converter. Returns row count."""
    frame = convert_teacher_excel(Path(excel_path), Path(csv_path))
    return len(frame)


def ingest_to_chroma(csv_path: str | Path = DEFAULT_CSV_PATH, persist_dir: str | Path | None = None) -> int:
    return ingest_orders_to_chroma(csv_path=csv_path, persist_dir=persist_dir)


def run_full_pipeline(
    excel_path: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    csv_path: str | Path = DEFAULT_CSV_PATH,
    persist_dir: str | Path | None = None,
    progress_callback: ProgressCallback = lambda step, status, detail: None,
) -> DataStatus:
    """Run build_db -> convert -> ingest in order, reporting progress each step.

    Any step that raises stops the pipeline (exception propagates to caller).
    """
    progress_callback("build_db", "running", "建立 SQLite 資料庫")
    counts = build_database(excel_path, db_path)
    progress_callback("build_db", "done", f"{len(counts)} 張表, {sum(counts.values())} 列")

    progress_callback("convert", "running", "產生 RAG 訂單 CSV")
    rows = convert_for_rag(excel_path, csv_path)
    progress_callback("convert", "done", f"{rows} 列")

    progress_callback("ingest", "running", "建立向量索引（首次需下載模型）")
    ingested = ingest_to_chroma(csv_path, persist_dir)
    progress_callback("ingest", "done", f"{ingested} 筆")

    return data_status(db_path=db_path, csv_path=csv_path, persist_dir=persist_dir)
