from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.convert_teacher_excel import OUTPUT_COLUMNS, convert_teacher_excel


def build_order_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "訂單明細編號": "ORD2026-00001",
                "訂單月份": "2026-01-01",
                "合約編號": "SC20006100",
                "客戶名稱": "測試客戶有限公司",
                "訂單日期": "2026-01-10",
                "交期": "2026-02-10",
                "產品料號": "P001",
                "產品說明": "600V XLPE-PVC 測試電纜",
                "產品族群": "CV",
                "芯數": "單芯",
                "截面積（平方毫米）": 100,
                "需求數量（噸）": 1.5,
                "需求銅量（公斤）": 1200.0,
                "是否新產品": "N",
                "優先等級": "A_急單",
                "客戶類型": "經銷商",
                "承諾類型": "標準交期",
                "計畫前置天數": 31,
                "標準需求前置天數": 28,
                "緩衝天數": 3,
                "訂單來源類型": "正式訂單",
            }
        ]
    )


def build_product_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "料號": "P001",
                "產品簡稱": "CV 大線",
                "是否標準品": "Y",
                "主要機台群組": "拉伸群/絞線群/押出群",
                "包裝方式": "木軸",
                "排程難度等級": "中",
                "每噸銅重係數": 0.78,
            }
        ]
    )


def build_risk_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "訂單明細編號": "ORD2026-00001",
                "前一產品族群": "IV",
                "預估換線工時": 1.6,
                "需求集中度分數": 48.8,
                "交期壓力分數": 79,
                "產品難度分數": 20,
                "物料風險分數": 25,
                "產能負載率": 4.475,
                "產能風險分數": 95,
                "換線風險分數": 17.6,
                "異常影響分數": 35.6,
                "優先級分數": 65,
                "綜合風險分數": 58.1,
                "是否高風險": "Y",
                "預估延誤天數": 0.7,
                "建議開工日": "2026-01-15",
                "預估完工日": "2026-02-09",
                "建議處置": "正常排程但需觀察",
            }
        ]
    )


def write_teacher_excel(
    excel_path: Path,
    orders: pd.DataFrame | None = None,
    products: pd.DataFrame | None = None,
    risks: pd.DataFrame | None = None,
) -> None:
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        (orders if orders is not None else build_order_rows()).to_excel(
            writer,
            sheet_name="01_訂單需求",
            index=False,
        )
        (products if products is not None else build_product_rows()).to_excel(
            writer,
            sheet_name="02_產品主檔",
            index=False,
        )
        (risks if risks is not None else build_risk_rows()).to_excel(
            writer,
            sheet_name="09_排程因素評估",
            index=False,
        )


def test_convert_teacher_excel_success(tmp_path: Path) -> None:
    excel_path = tmp_path / "teacher_orders.xlsx"
    output_path = tmp_path / "teacher_orders_for_rag.csv"

    write_teacher_excel(excel_path)

    result = convert_teacher_excel(excel_path, output_path)

    assert output_path.exists()
    assert len(result) == 1
    assert list(result.columns) == OUTPUT_COLUMNS

    row = result.iloc[0]
    assert row["record_source"] == "teacher_cable_orders"
    assert row["order_id"] == "ORD2026-00001"
    assert row["product_family"] == "CV"
    assert row["overall_risk_score"] == 58.1
    assert "客戶=測試客戶有限公司" in row["spec_summary"]
    assert "產品族群=CV" in row["spec_summary"]
    assert "建議處置=正常排程但需觀察" in row["spec_summary"]


def test_convert_teacher_excel_missing_required_column_raises(tmp_path: Path) -> None:
    excel_path = tmp_path / "teacher_orders.xlsx"
    output_path = tmp_path / "teacher_orders_for_rag.csv"
    orders = build_order_rows().drop(columns=["客戶名稱"])

    write_teacher_excel(excel_path, orders=orders)

    with pytest.raises(ValueError, match="missing required columns"):
        convert_teacher_excel(excel_path, output_path)


def test_convert_teacher_excel_duplicate_product_id_raises(tmp_path: Path) -> None:
    excel_path = tmp_path / "teacher_orders.xlsx"
    output_path = tmp_path / "teacher_orders_for_rag.csv"
    products = pd.concat([build_product_rows(), build_product_rows()], ignore_index=True)

    write_teacher_excel(excel_path, products=products)

    with pytest.raises(ValueError, match="duplicated values"):
        convert_teacher_excel(excel_path, output_path)


def test_convert_teacher_excel_missing_risk_match_raises(tmp_path: Path) -> None:
    excel_path = tmp_path / "teacher_orders.xlsx"
    output_path = tmp_path / "teacher_orders_for_rag.csv"
    risks = build_risk_rows()
    risks.loc[0, "訂單明細編號"] = "ORD2026-99999"

    write_teacher_excel(excel_path, risks=risks)

    with pytest.raises(ValueError, match="schedule risk data"):
        convert_teacher_excel(excel_path, output_path)
