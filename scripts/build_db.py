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
