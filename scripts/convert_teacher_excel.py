from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_EXCEL_PATH = Path("data/線纜製造排程資料集_半年訂單.xlsx")
DEFAULT_OUTPUT_PATH = Path("data/teacher_orders_for_rag.csv")

ORDER_SHEET = "01_訂單需求"
PRODUCT_SHEET = "02_產品主檔"
RISK_SHEET = "09_排程因素評估"

COLLECTION_SOURCE = "teacher_cable_orders"

ORDER_COLUMN_MAPPING = {
    "訂單明細編號": "order_id",
    "訂單月份": "order_month",
    "合約編號": "contract_id",
    "客戶名稱": "customer",
    "訂單日期": "order_date",
    "交期": "due_date",
    "產品料號": "product_id",
    "產品說明": "product_description",
    "產品族群": "product_family",
    "芯數": "core_count",
    "截面積（平方毫米）": "section_area_mm2",
    "需求數量（噸）": "quantity_ton",
    "需求銅量（公斤）": "copper_kg",
    "是否新產品": "is_new_product",
    "優先等級": "priority",
    "客戶類型": "customer_type",
    "承諾類型": "promise_type",
    "計畫前置天數": "planned_lead_days",
    "標準需求前置天數": "standard_lead_days",
    "緩衝天數": "buffer_days",
    "訂單來源類型": "order_source_type",
}

PRODUCT_COLUMN_MAPPING = {
    "料號": "product_id",
    "產品簡稱": "product_short_name",
    "是否標準品": "is_standard_product",
    "主要機台群組": "main_machine_groups",
    "包裝方式": "packaging_type",
    "排程難度等級": "schedule_difficulty_level",
    "每噸銅重係數": "copper_weight_factor",
}

RISK_COLUMN_MAPPING = {
    "訂單明細編號": "order_id",
    "前一產品族群": "previous_product_family",
    "預估換線工時": "estimated_changeover_hours",
    "需求集中度分數": "demand_concentration_score",
    "交期壓力分數": "due_pressure_score",
    "產品難度分數": "product_difficulty_score",
    "物料風險分數": "material_risk_score",
    "產能負載率": "capacity_load_rate",
    "產能風險分數": "capacity_risk_score",
    "換線風險分數": "changeover_risk_score",
    "異常影響分數": "downtime_impact_score",
    "優先級分數": "priority_score",
    "綜合風險分數": "overall_risk_score",
    "是否高風險": "is_high_risk",
    "預估延誤天數": "estimated_delay_days",
    "建議開工日": "suggested_start_date",
    "預估完工日": "estimated_finish_date",
    "建議處置": "recommended_action",
}

PRODUCT_COLUMNS = [
    "product_id",
    "product_short_name",
    "is_standard_product",
    "main_machine_groups",
    "packaging_type",
    "schedule_difficulty_level",
    "copper_weight_factor",
]

RISK_COLUMNS = [
    "order_id",
    "previous_product_family",
    "estimated_changeover_hours",
    "demand_concentration_score",
    "due_pressure_score",
    "product_difficulty_score",
    "material_risk_score",
    "capacity_load_rate",
    "capacity_risk_score",
    "changeover_risk_score",
    "downtime_impact_score",
    "priority_score",
    "overall_risk_score",
    "is_high_risk",
    "estimated_delay_days",
    "suggested_start_date",
    "estimated_finish_date",
    "recommended_action",
]

DATE_COLUMNS = [
    "order_month",
    "order_date",
    "due_date",
    "suggested_start_date",
    "estimated_finish_date",
]

OUTPUT_COLUMNS = [
    "record_source",
    "order_id",
    "order_month",
    "contract_id",
    "customer",
    "order_date",
    "due_date",
    "product_id",
    "product_description",
    "product_family",
    "product_short_name",
    "core_count",
    "section_area_mm2",
    "quantity_ton",
    "copper_kg",
    "is_new_product",
    "is_standard_product",
    "priority",
    "customer_type",
    "promise_type",
    "planned_lead_days",
    "standard_lead_days",
    "buffer_days",
    "order_source_type",
    "main_machine_groups",
    "packaging_type",
    "schedule_difficulty_level",
    "copper_weight_factor",
    "previous_product_family",
    "estimated_changeover_hours",
    "demand_concentration_score",
    "due_pressure_score",
    "product_difficulty_score",
    "material_risk_score",
    "capacity_load_rate",
    "capacity_risk_score",
    "changeover_risk_score",
    "downtime_impact_score",
    "priority_score",
    "overall_risk_score",
    "is_high_risk",
    "estimated_delay_days",
    "suggested_start_date",
    "estimated_finish_date",
    "recommended_action",
    "spec_summary",
]

SUMMARY_FIELDS = [
    ("客戶", "customer", ""),
    ("產品族群", "product_family", ""),
    ("產品", "product_description", ""),
    ("產品簡稱", "product_short_name", ""),
    ("芯數", "core_count", ""),
    ("截面積", "section_area_mm2", "平方毫米"),
    ("需求數量", "quantity_ton", "噸"),
    ("需求銅量", "copper_kg", "公斤"),
    ("優先等級", "priority", ""),
    ("客戶類型", "customer_type", ""),
    ("承諾類型", "promise_type", ""),
    ("緩衝天數", "buffer_days", "天"),
    ("物料風險", "material_risk_score", ""),
    ("產能風險", "capacity_risk_score", ""),
    ("換線風險", "changeover_risk_score", ""),
    ("綜合風險", "overall_risk_score", ""),
    ("是否高風險", "is_high_risk", ""),
    ("預估延誤", "estimated_delay_days", "天"),
    ("建議處置", "recommended_action", ""),
]


def validate_file_exists(file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"Input Excel file not found: {file_path}")


def validate_required_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    sheet_name: str,
) -> None:
    missing_columns = [column for column in required_columns if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(f"Sheet '{sheet_name}' is missing required columns: {missing_columns}")


def validate_unique_key(dataframe: pd.DataFrame, key_column: str, sheet_name: str) -> None:
    duplicated_count = dataframe[key_column].duplicated().sum()
    if duplicated_count > 0:
        raise ValueError(
            f"Sheet '{sheet_name}' has {duplicated_count} duplicated values "
            f"in key column '{key_column}'."
        )


def read_and_rename_sheet(
    excel_path: Path,
    sheet_name: str,
    column_mapping: dict[str, str],
) -> pd.DataFrame:
    dataframe = pd.read_excel(excel_path, sheet_name=sheet_name)
    validate_required_columns(dataframe, list(column_mapping.keys()), sheet_name)
    return dataframe.rename(columns=column_mapping)


def normalize_date_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()

    for column in DATE_COLUMNS:
        if column not in result.columns:
            continue

        converted = pd.to_datetime(result[column], errors="coerce")
        result[column] = converted.dt.strftime("%Y-%m-%d").fillna("")

    return result


def format_summary_value(value: Any) -> str:
    if pd.isna(value):
        return "N/A"

    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()

    if isinstance(value, float):
        return f"{value:g}"

    return str(value).strip()


def build_spec_summary(row: pd.Series) -> str:
    parts = []

    for label, column, suffix in SUMMARY_FIELDS:
        value = format_summary_value(row.get(column, ""))
        parts.append(f"{label}={value}{suffix}")

    return "；".join(parts)


def validate_merge_quality(
    merged: pd.DataFrame,
    expected_rows: int,
) -> None:
    if len(merged) != expected_rows:
        raise ValueError(f"Merged row count mismatch. Expected {expected_rows}, got {len(merged)}.")

    missing_product_count = merged["product_short_name"].isna().sum()
    if missing_product_count > 0:
        raise ValueError(
            f"{missing_product_count} orders could not be matched to product master data."
        )

    missing_risk_count = merged["overall_risk_score"].isna().sum()
    if missing_risk_count > 0:
        raise ValueError(f"{missing_risk_count} orders could not be matched to schedule risk data.")


def convert_teacher_excel(excel_path: Path, output_path: Path) -> pd.DataFrame:
    validate_file_exists(excel_path)

    orders = read_and_rename_sheet(excel_path, ORDER_SHEET, ORDER_COLUMN_MAPPING)
    products = read_and_rename_sheet(excel_path, PRODUCT_SHEET, PRODUCT_COLUMN_MAPPING)
    risks = read_and_rename_sheet(excel_path, RISK_SHEET, RISK_COLUMN_MAPPING)

    validate_unique_key(orders, "order_id", ORDER_SHEET)
    validate_unique_key(products, "product_id", PRODUCT_SHEET)
    validate_unique_key(risks, "order_id", RISK_SHEET)

    validate_required_columns(products, PRODUCT_COLUMNS, PRODUCT_SHEET)
    validate_required_columns(risks, RISK_COLUMNS, RISK_SHEET)

    expected_rows = len(orders)

    merged = orders.merge(products[PRODUCT_COLUMNS], on="product_id", how="left")
    merged = merged.merge(risks[RISK_COLUMNS], on="order_id", how="left")

    validate_merge_quality(merged, expected_rows)

    merged = normalize_date_columns(merged)
    merged["record_source"] = COLLECTION_SOURCE
    merged["spec_summary"] = merged.apply(build_spec_summary, axis=1)

    validate_required_columns(merged, OUTPUT_COLUMNS, "merged output")

    result = merged[OUTPUT_COLUMNS].copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, encoding="utf-8-sig")

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert teacher cable manufacturing Excel data into a RAG-ready CSV."
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=DEFAULT_EXCEL_PATH,
        help=f"Input Excel path. Default: {DEFAULT_EXCEL_PATH}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output CSV path. Default: {DEFAULT_OUTPUT_PATH}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = convert_teacher_excel(args.excel, args.output)

    print(f"Saved: {args.output}")
    print(f"Rows: {len(result)}")
    print(f"Columns: {len(result.columns)}")


if __name__ == "__main__":
    main()
