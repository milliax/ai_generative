# Data-Onboarding UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Streamlit panel that detects missing data on startup, guides the user to drop the teacher xlsx into `raw_data/` and one-click convert it (with progress animation) into both a SQLite DB and a ChromaDB vector index, then opens the full coordination panel backed by a stub orchestrator.

**Architecture:** Conversion logic lives in pure (UI-free) modules — `scripts/build_db.py` (xlsx→SQLite) and `shared/data_pipeline.py` (status + 3-step orchestration), reusing the existing `convert_teacher_excel.py` and `pricing/ingest.py`. `ui/streamlit_app.py` only calls the pipeline and renders. A stub `agents/orchestrator.py` returns a `CoordinationPlan`, calling the real `pricing.retrieval.retrieve_similar` for reference orders.

**Tech Stack:** Python 3.11+, pandas, sqlite3 (stdlib), ChromaDB, sentence-transformers, Pydantic, Streamlit, pytest.

---

## File Structure

- Create `scripts/build_db.py` — read 9 xlsx sheets → `data/supply_chain.db`, one table per sheet, indexes on keys. Pure functions + CLI.
- Create `shared/data_pipeline.py` — `DataStatus`, `find_raw_excel`, `data_status`, three step-wrappers, `run_full_pipeline`. The only interface between UI and conversion. No Streamlit import.
- Create `agents/orchestrator.py` — stub `run_orchestrator(OrderRequest) -> CoordinationPlan`; real `retrieve_similar` for `reference_orders`, canned for the rest.
- Create `ui/streamlit_app.py` — startup gate (3 cases) + conversion animation + main panel.
- Create `tests/test_build_db.py`, `tests/test_data_pipeline.py`, `tests/test_orchestrator_stub.py`.
- Modify `.gitignore` — add `*.db` (currently only `*.sqlite3` is ignored).
- Modify `README.md` — add the two new modules to the structure tree.

**Do NOT modify:** `scripts/convert_teacher_excel.py`, `pricing/ingest.py`, `pricing/retrieval.py`, `shared/models.py`.

**Key existing interfaces this plan calls:**
- `convert_teacher_excel(excel_path: Path, output_path: Path) -> pd.DataFrame` (`scripts/convert_teacher_excel.py:273`)
- `ingest_orders_to_chroma(csv_path=..., persist_dir=None, collection_name="historical_orders") -> int` (`pricing/ingest.py:178`)
- `retrieve_similar(query: str, k: int = 5, persist_dir=None, collection_name="historical_orders") -> list[dict]` (`pricing/retrieval.py:62`)
- `get_persist_dir(persist_dir=None) -> str` (`pricing/ingest.py:28`) — honors `CHROMA_PERSIST_DIR`
- `OrderRequest`, `CoordinationPlan`, `CapacityStatus`, `Urgency` (`shared/models.py`)

**The 9 sheets → table-name mapping (used in Task 1):**

```python
SHEET_TABLE_MAP = {
    "01_訂單需求": "orders",
    "02_產品主檔": "products",
    "03_產品製程路徑": "process_routes",
    "04_機台主檔": "machines",
    "05_機台週產能": "machine_weekly_capacity",
    "06_物料月度庫存": "material_monthly_inventory",
    "07_換線矩陣": "changeover_matrix",
    "08_異常停機": "downtime_events",
    "09_排程因素評估": "schedule_risk",
}
INDEX_SPECS = {
    "orders": ["訂單明細編號", "產品料號"],
    "products": ["料號"],
    "process_routes": ["產品族群"],
    "machines": ["機台編號"],
    "machine_weekly_capacity": ["機台編號", "週起始日"],
    "schedule_risk": ["訂單明細編號"],
}
```

---

### Task 1: `scripts/build_db.py` — xlsx → SQLite

**Files:**
- Create: `scripts/build_db.py`
- Test: `tests/test_build_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_db.py
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_db import SHEET_TABLE_MAP, build_database

SHEETS = list(SHEET_TABLE_MAP.keys())


def _make_mini_xlsx(path: Path) -> None:
    """Write a mini 9-sheet workbook with fake (non-real) data."""
    frames = {
        "01_訂單需求": pd.DataFrame(
            {"訂單明細編號": ["O1", "O2"], "產品料號": ["P1", "P2"], "需求數量（噸）": [1.0, 2.0]}
        ),
        "02_產品主檔": pd.DataFrame({"料號": ["P1", "P2"], "產品族群": ["IV", "CV"]}),
        "03_產品製程路徑": pd.DataFrame({"產品族群": ["IV"], "製程步驟": ["拉伸"]}),
        "04_機台主檔": pd.DataFrame({"機台編號": ["M1"], "機台名稱": ["拉伸機"]}),
        "05_機台週產能": pd.DataFrame({"機台編號": ["M1"], "週起始日": ["2026-01-05"], "產能（噸）": [50.0]}),
        "06_物料月度庫存": pd.DataFrame({"物料編號": ["MAT_CU"], "月底可用量（公斤）": [1000.0]}),
        "07_換線矩陣": pd.DataFrame({"前一產品族群": ["IV"], "下一產品族群": ["CV"]}),
        "08_異常停機": pd.DataFrame({"事件編號": ["DT1"], "機台編號": ["M1"]}),
        "09_排程因素評估": pd.DataFrame({"訂單明細編號": ["O1"], "綜合風險分數": [54.6]}),
    }
    with pd.ExcelWriter(path) as writer:
        for sheet, df in frames.items():
            df.to_excel(writer, sheet_name=sheet, index=False)


def test_build_database_creates_all_tables(tmp_path):
    xlsx = tmp_path / "mini.xlsx"
    _make_mini_xlsx(xlsx)
    db = tmp_path / "out.db"

    counts = build_database(xlsx, db)

    assert db.exists()
    assert counts["orders"] == 2
    assert counts["machines"] == 1
    assert set(counts.keys()) == set(SHEET_TABLE_MAP.values())


def test_build_database_table_is_queryable(tmp_path):
    import sqlite3

    xlsx = tmp_path / "mini.xlsx"
    _make_mini_xlsx(xlsx)
    db = tmp_path / "out.db"
    build_database(xlsx, db)

    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT 訂單明細編號 FROM orders ORDER BY 訂單明細編號").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["O1", "O2"]


def test_build_database_creates_index(tmp_path):
    import sqlite3

    xlsx = tmp_path / "mini.xlsx"
    _make_mini_xlsx(xlsx)
    db = tmp_path / "out.db"
    build_database(xlsx, db)

    conn = sqlite3.connect(db)
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders'"
    ).fetchall()
    conn.close()
    assert len(idx) >= 1


def test_build_database_missing_sheet_raises(tmp_path):
    xlsx = tmp_path / "bad.xlsx"
    pd.DataFrame({"a": [1]}).to_excel(xlsx, sheet_name="01_訂單需求", index=False)
    db = tmp_path / "out.db"

    with pytest.raises(ValueError, match="缺少工作表"):
        build_database(xlsx, db)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_build_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_db'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/build_db.py
"""Build a relational SQLite database from the teacher's 9-sheet cable Excel.

One table per sheet. Chinese column names are preserved (MVP). Indexes are
created on the key columns used by downstream Capacity / ESG queries.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_DB_PATH = Path("data/supply_chain.db")

SHEET_TABLE_MAP = {
    "01_訂單需求": "orders",
    "02_產品主檔": "products",
    "03_產品製程路徑": "process_routes",
    "04_機台主檔": "machines",
    "05_機台週產能": "machine_weekly_capacity",
    "06_物料月度庫存": "material_monthly_inventory",
    "07_換線矩陣": "changeover_matrix",
    "08_異常停機": "downtime_events",
    "09_排程因素評估": "schedule_risk",
}

INDEX_SPECS = {
    "orders": ["訂單明細編號", "產品料號"],
    "products": ["料號"],
    "process_routes": ["產品族群"],
    "machines": ["機台編號"],
    "machine_weekly_capacity": ["機台編號", "週起始日"],
    "schedule_risk": ["訂單明細編號"],
}


def build_database(excel_path: str | Path, db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, int]:
    """Read every sheet into its own SQLite table and return per-table row counts."""
    excel_path = Path(excel_path)
    db_path = Path(db_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel 檔不存在: {excel_path}")

    workbook = pd.read_excel(excel_path, sheet_name=None)
    missing = [s for s in SHEET_TABLE_MAP if s not in workbook]
    if missing:
        raise ValueError(f"缺少工作表: {missing}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    conn = sqlite3.connect(db_path)
    try:
        for sheet, table in SHEET_TABLE_MAP.items():
            frame = workbook[sheet]
            frame.to_sql(table, conn, if_exists="replace", index=False)
            counts[table] = len(frame)
            for column in INDEX_SPECS.get(table, []):
                if column in frame.columns:
                    safe = column.replace('"', '""')
                    idx_name = f"idx_{table}_{abs(hash(column)) % 100000}"
                    conn.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ("{safe}")')
        conn.commit()
    finally:
        conn.close()
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SQLite DB from teacher cable Excel.")
    parser.add_argument("--excel", type=Path, required=True, help="Input xlsx path.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help=f"Output DB. Default: {DEFAULT_DB_PATH}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = build_database(args.excel, args.db)
    total = sum(counts.values())
    print(f"Built {args.db} with {len(counts)} tables, {total} rows total.")
    for table, n in counts.items():
        print(f"  {table}: {n}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_build_db.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/build_db.py tests/test_build_db.py
git commit -m "feat(data): add build_db.py to convert teacher xlsx into SQLite"
```

---

### Task 2: `.gitignore` — ignore `*.db`

**Files:**
- Modify: `.gitignore` (the `# Data` block, after `*.parquet`)

- [ ] **Step 1: Make the change**

Add `*.db` immediately after the `*.parquet` line in the `# Data` section:

```
*.parquet
*.db
```

- [ ] **Step 2: Verify it is ignored**

Run: `touch data/supply_chain.db && git check-ignore data/supply_chain.db`
Expected: prints `data/supply_chain.db` (it is ignored). Then `rm data/supply_chain.db`.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore *.db so SQLite data never enters the repo"
```

---

### Task 3: `shared/data_pipeline.py` — status + step wrappers

**Files:**
- Create: `shared/data_pipeline.py`
- Test: `tests/test_data_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_data_pipeline.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_data_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'shared.data_pipeline'`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/data_pipeline.py
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
    with csv_path.open(encoding="utf-8") as handle:
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
    """Convert xlsx → RAG CSV using the existing converter. Returns row count."""
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
    """Run build_db → convert → ingest in order, reporting progress each step.

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
```

> Note: the test monkeypatches `build_database`, `convert_for_rag`, `ingest_to_chroma` as module attributes of `data_pipeline`, so `run_full_pipeline` must call them as bare names (it does, via the imports above).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_data_pipeline.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add shared/data_pipeline.py tests/test_data_pipeline.py
git commit -m "feat(data): add data_pipeline with status detection and 3-step conversion"
```

---

### Task 4: `agents/orchestrator.py` — stub with real retrieval

**Files:**
- Create: `agents/orchestrator.py`
- Test: `tests/test_orchestrator_stub.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrator_stub.py
from datetime import datetime

from shared.models import CoordinationPlan, OrderRequest
from agents import orchestrator


def _order() -> OrderRequest:
    return OrderRequest(
        customer="測試客戶",
        raw_text="需要 100 噸 CV 250mm2 電纜，兩週內交貨",
        received_at=datetime(2026, 5, 30, 10, 0, 0),
        urgency="rush",
    )


def test_run_orchestrator_returns_valid_plan(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "retrieve_similar",
        lambda query, k=3, **kw: [{"order_id": "O1", "similarity": 0.9, "matched_summary": "x"}],
    )
    plan = orchestrator.run_orchestrator(_order())
    assert isinstance(plan, CoordinationPlan)
    assert plan.reference_orders == [{"order_id": "O1", "similarity": 0.9, "matched_summary": "x"}]


def test_run_orchestrator_degrades_when_retrieval_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("chroma down")

    monkeypatch.setattr(orchestrator, "retrieve_similar", boom)
    plan = orchestrator.run_orchestrator(_order())
    assert isinstance(plan, CoordinationPlan)
    assert plan.reference_orders == []
    assert any("RAG" in r or "檢索" in r for r in plan.risks)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_orchestrator_stub.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.orchestrator'`

- [ ] **Step 3: Write minimal implementation**

```python
# agents/orchestrator.py
"""W1 STUB orchestrator — replace with the real LangGraph version in Agent Task 6.

Interface matches the real one: run_orchestrator(OrderRequest) -> CoordinationPlan.
Pricing reference orders come from the REAL pricing RAG; everything else is canned.
"""

from __future__ import annotations

from datetime import date

from pricing.retrieval import retrieve_similar
from shared.models import CoordinationPlan, OrderRequest


def _build_query(order: OrderRequest) -> str:
    """Build a retrieval query from the order text (approximates spec_summary)."""
    parts = [order.customer, order.raw_text]
    if order.urgency is not None:
        parts.append(order.urgency)  # Urgency is a Literal[str]
    return " ".join(p for p in parts if p)


def run_orchestrator(order: OrderRequest) -> CoordinationPlan:
    """Return a coordination plan. Pricing RAG is real; other fields are stubbed."""
    risks: list[str] = []
    try:
        reference_orders = retrieve_similar(_build_query(order), k=3)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully for the demo
        reference_orders = []
        risks.append(f"RAG 檢索暫時無法使用（{type(exc).__name__}），參考歷史訂單從缺")

    return CoordinationPlan(
        estimated_price=0.0,  # W1 stub
        price_confidence=(0.0, 0.0),  # W1 stub
        estimated_delivery=date(2026, 8, 15),  # W1 stub
        carbon_footprint_kg=0.0,  # W1 stub
        capacity_status="OK",  # W1 stub (CapacityStatus = Literal["OK","OVERLOAD"])
        alternative_suppliers=[],  # W1 stub
        reference_orders=reference_orders,
        risks=risks,
        next_actions=["W1 stub：等 Agent 組 Task 6 接真實 orchestrator"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_orchestrator_stub.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/orchestrator.py tests/test_orchestrator_stub.py
git commit -m "feat(agents): add stub orchestrator wired to real pricing retrieval"
```

---

### Task 5: `ui/streamlit_app.py` — gate + conversion + main panel

**Files:**
- Create: `ui/streamlit_app.py`

This task has no automated tests (per spec — UI uses a manual acceptance checklist). Each step is a coherent block; verify by running the app.

- [ ] **Step 1: Write the app**

```python
# ui/streamlit_app.py
"""Streamlit panel: startup data-onboarding gate + main coordination panel.

Run: streamlit run ui/streamlit_app.py
UI rules: no litellm import, no business logic, no hardcoded .env, no schema changes.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from agents.orchestrator import run_orchestrator
from shared.data_pipeline import DEFAULT_RAW_DIR, data_status, run_full_pipeline
from shared.models import OrderRequest

URGENCY_OPTIONS = ["normal", "rush", "emergency"]  # Urgency = Literal[...] in shared/models

DEMO_SCENARIOS = {
    "（自訂）": "",
    "正常單": "AWS Q3 訂單：1000 噸 CV 250mm2 電纜，8 月底前交貨",
    "急單": "Meta 緊急加單：兩週內需要 500 噸 IV 100mm2，產線可能要外援",
    "規格變更": "原 Google 訂單規格變更：芯數從單芯改雙芯，數量不變，重新評估",
}

STEP_LABELS = {
    "build_db": "建立 SQLite 資料庫",
    "convert": "產生 RAG 訂單 CSV",
    "ingest": "建立向量索引",
}

st.set_page_config(page_title="綠色供應鏈協調系統", page_icon="🌱", layout="wide")


def render_gate(status) -> None:
    if status.raw_excel_path is None:
        st.warning("🗂️ 尚未載入資料")
        st.write(f"請將老師的 Excel 放到 `{DEFAULT_RAW_DIR}/` 後按下方按鈕。")
        st.button("🔄 重新偵測", on_click=st.rerun)
        return

    st.success(f"✅ 偵測到：{status.raw_excel_path.name}")
    st.caption("9 個工作表 · 約 3000 筆訂單")
    if st.button("⚙️ 開始轉檔"):
        _run_conversion(status.raw_excel_path)


def _run_conversion(excel_path) -> None:
    with st.status("⚙️ 資料轉檔中…", expanded=True) as box:
        def on_progress(step: str, state: str, detail: str) -> None:
            label = STEP_LABELS.get(step, step)
            if state == "running":
                box.write(f"🔄 {label}…（{detail}）")
            elif state == "done":
                box.write(f"✅ {label}（{detail}）")

        try:
            run_full_pipeline(excel_path=excel_path, progress_callback=on_progress)
            box.update(label="✅ 轉檔完成", state="complete")
        except Exception as exc:  # noqa: BLE001 — show the failing step to the user
            box.update(label="❌ 轉檔失敗", state="error")
            st.error(f"轉檔失敗：{type(exc).__name__}: {exc}")
            st.button("🔁 重試", on_click=st.rerun)
            return
    st.balloons()
    st.button("✅ 進入系統", on_click=st.rerun)


def render_sidebar(status) -> None:
    with st.sidebar:
        st.header("資料狀態")
        st.metric("SQLite 表數", status.db_tables)
        st.metric("RAG CSV 列數", status.csv_rows)
        st.metric("向量索引筆數", status.chroma_count)
        if st.button("♻️ 重建資料"):
            st.session_state.pop("plan", None)
            st.rerun()


def render_main_panel() -> None:
    st.title("🌱 多 Agent 綠色供應鏈協調系統")
    left, mid = st.columns([1, 2])

    with left:
        st.subheader("客戶需求輸入")
        scenario = st.selectbox("Demo 情境", list(DEMO_SCENARIOS.keys()))
        customer = st.text_input("客戶", value="AWS")
        raw_text = st.text_area("需求", value=DEMO_SCENARIOS[scenario], height=120)
        urgency = st.selectbox("急迫度", URGENCY_OPTIONS)
        if st.button("▶ 跑 Agent"):
            order = OrderRequest(
                customer=customer,
                raw_text=raw_text,
                received_at=datetime.now(),
                urgency=urgency,
            )
            with st.status("🤖 Agents 協調中…", expanded=False):
                st.session_state["plan"] = run_orchestrator(order)

    with mid:
        st.subheader("協調報告")
        plan = st.session_state.get("plan")
        if plan is None:
            st.info("輸入需求後點「▶ 跑 Agent」。")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 預估報價", f"${plan.estimated_price:,.0f}")
            c2.metric("📅 交期", str(plan.estimated_delivery))
            c3.metric("🌱 碳排", f"{plan.carbon_footprint_kg:,.0f} kg")
            st.markdown("**📊 參考歷史訂單**")
            if plan.reference_orders:
                st.dataframe(plan.reference_orders, use_container_width=True)
            else:
                st.caption("（無參考訂單）")
            if plan.risks:
                for risk in plan.risks:
                    st.warning(risk)


def main() -> None:
    status = data_status()
    if not (status.db_ready and status.csv_ready and status.chroma_ready):
        render_gate(status)
        return
    render_sidebar(status)
    render_main_panel()


main()
```

- [ ] **Step 2: Smoke-check imports (no Streamlit runtime)**

Run: `.venv/bin/python -c "import ast; ast.parse(open('ui/streamlit_app.py').read()); print('syntax OK')"`
Expected: `syntax OK`

- [ ] **Step 3: Manual run — gate path**

Ensure no data exists: `rm -f data/supply_chain.db data/teacher_orders_for_rag.csv && rm -rf chroma_db`
Run: `.venv/bin/streamlit run ui/streamlit_app.py`
Expected: with `raw_data/*.xlsx` present → "✅ 偵測到 …" + 「開始轉檔」. Click it → three progress lines turn green → balloons → 進入系統 → main panel.

- [ ] **Step 4: Manual run — main panel path**

In the panel: pick "急單" scenario → 「▶ 跑 Agent」 → report card shows + 「參考歷史訂單」 populated from the real ChromaDB. Sidebar shows non-zero table / CSV / vector counts.

- [ ] **Step 5: Commit**

```bash
git add ui/streamlit_app.py
git commit -m "feat(ui): add Streamlit data-onboarding gate and coordination panel"
```

---

### Task 6: README structure update

**Files:**
- Modify: `README.md` (the project structure tree, around `pricing/` lines)

- [ ] **Step 1: Update the structure tree**

In the structure tree, add the two new modules near `pricing/`:

```
├── scripts/
│   ├── convert_teacher_excel.py    # 老師 xlsx → RAG CSV
│   └── build_db.py                 # 老師 xlsx → SQLite (9 表)
├── shared/
│   └── data_pipeline.py            # 啟動偵測 + 轉檔串接（UI 唯一介面）
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add build_db and data_pipeline to README structure"
```

---

### Task 7: Full suite green + discussion log

**Files:**
- Create: `docs/discussions/2026-05-30-data-onboarding-ui.md`

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — all prior tests (42) plus the new build_db (4) + data_pipeline (7) + orchestrator (2) = 55 passed.

- [ ] **Step 2: Write the discussion log**

```markdown
# 2026-05-30 資料導入 UI 與轉檔流程實作

## 參與者
- Max、Claude

## 主題
實作啟動時的資料導入 gate + 轉檔（xlsx → SQLite + ChromaDB）+ 完整 Streamlit panel（接 stub orchestrator）。

## 主要決定
- 資料全程不進 repo（public repo + 真實客戶資料）；`.gitignore` 補 `*.db`。
- 轉檔邏輯放 `shared/data_pipeline.py`（純函式），UI 只呼叫。
- SQLite 一表一 sheet，欄名 MVP 保留中文。
- stub orchestrator 的 Pricing 段走真實 `retrieve_similar`，其餘罐頭。

## 對 spec / README 的影響
- 依 `docs/superpowers/specs/2026-05-30-data-onboarding-ui-design.md` 實作。
- README 結構圖補上 build_db.py 與 data_pipeline.py。

## 待辦
- Agent 組 Task 6 完成後，用真 orchestrator 替換 stub（介面已對齊）。
- Capacity/ESG 接手後決定 SQLite 欄名是否正規化成英文。
```

- [ ] **Step 3: Commit**

```bash
git add docs/discussions/2026-05-30-data-onboarding-ui.md
git commit -m "docs: add discussion log for data-onboarding UI implementation"
```

---

## Self-Review

**Spec coverage:**
- Startup gate (3 cases) → Task 5 ✅
- xlsx→SQLite (9 tables + indexes) → Task 1 ✅
- xlsx→CSV→Chroma reuse → Task 3 (`convert_for_rag`/`ingest_to_chroma`) ✅
- `data_status` detection → Task 3 ✅
- Conversion animation → Task 5 (`st.status` + progress_callback) ✅
- stub orchestrator with real retrieval + graceful degrade → Task 4 ✅
- main panel (sidebar/left/mid/trace) → Task 5 ✅
- `.gitignore` `*.db` → Task 2 ✅
- tests for build_db / data_pipeline / orchestrator → Tasks 1,3,4 ✅
- README update → Task 6 ✅
- not modifying convert/ingest/retrieval/models → respected (only imported) ✅

**Placeholder scan:** No TBD/TODO-as-work. The `# W1 stub` comments are intentional, matching the spec's stub decision. All code steps show full code.

**Type consistency:** `DataStatus` fields (`db_ready`, `csv_ready`, `chroma_ready`, `db_tables`, `csv_rows`, `chroma_count`, `raw_excel_path`) are consistent across Task 3 definition and Task 5 usage. `run_full_pipeline(excel_path, ..., progress_callback)` and the `(step, status, detail)` callback signature match between Tasks 3 and 5. `run_orchestrator(OrderRequest) -> CoordinationPlan` consistent across Tasks 4 and 5. `build_database`/`convert_for_rag`/`ingest_to_chroma` names match between definition (Task 3) and monkeypatch targets (test in Task 3).

**Note on test counts:** "42 prior" assumes the merged main baseline. If the count differs, the absolute new-test additions (4+7+2=13) are what matter.
