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
