import csv
import random
from datetime import date
from pathlib import Path

import pytest

from scripts.generate_mock_orders import (
    CHASSIS_OPTIONS,
    DEFAULT_ORDER_COUNT,
    REQUIRED_COLUMNS,
    generate_mock_order,
    generate_mock_orders,
    write_mock_orders,
)


REQUIRED_COLUMN_SET = set(REQUIRED_COLUMNS)
MIN_UNIQUE_VALUES_FOR_VARIATION_CHECK = int(DEFAULT_ORDER_COUNT * 0.8)


def rows_from_orders(
    count: int = DEFAULT_ORDER_COUNT,
    seed: int = 42,
) -> list[dict[str, str | int | float]]:
    """Return generated orders as CSV-compatible rows for assertions."""
    return [order.to_csv_row() for order in generate_mock_orders(count=count, seed=seed)]


def assert_order_row_has_required_contract(row: dict[str, str | int | float]) -> None:
    """Assert one generated order row follows the expected CSV contract."""
    assert set(row) == REQUIRED_COLUMN_SET

    assert isinstance(row["order_id"], str)
    assert row["order_id"].startswith("MOCK-")

    assert isinstance(row["customer"], str)
    assert row["customer"]

    assert isinstance(row["cpu_sku"], str)
    assert row["cpu_sku"]

    assert isinstance(row["memory_gb"], int)
    assert row["memory_gb"] > 0

    assert isinstance(row["storage_tb"], int)
    assert row["storage_tb"] >= 0

    assert isinstance(row["chassis"], str)
    assert row["chassis"] in CHASSIS_OPTIONS

    assert isinstance(row["quantity"], int)
    assert row["quantity"] > 0

    assert isinstance(row["delivered_at"], str)
    date.fromisoformat(row["delivered_at"])

    assert isinstance(row["final_price"], float)
    assert row["final_price"] > 0

    assert isinstance(row["carbon_kg"], float)
    assert row["carbon_kg"] > 0

    assert isinstance(row["spec_summary"], str)
    assert row["spec_summary"]


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    """Read generated CSV rows from disk."""
    with csv_path.open("r", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_generate_mock_orders_default_count():
    orders = generate_mock_orders()

    assert len(orders) == DEFAULT_ORDER_COUNT


def test_generate_mock_orders_custom_count():
    orders = generate_mock_orders(count=7)

    assert len(orders) == 7


@pytest.mark.parametrize("invalid_count", [0, -1])
def test_generate_mock_orders_rejects_invalid_count(invalid_count: int):
    with pytest.raises(ValueError, match="count must be"):
        generate_mock_orders(count=invalid_count)


def test_generate_mock_orders_are_reproducible_with_same_seed():
    first_run = rows_from_orders(seed=123)
    second_run = rows_from_orders(seed=123)

    assert first_run == second_run


def test_different_seeds_generate_different_orders():
    first_run = rows_from_orders(seed=1)
    second_run = rows_from_orders(seed=2)

    assert first_run != second_run


def test_generated_order_rows_follow_required_contract():
    rows = rows_from_orders(count=10, seed=42)

    for row in rows:
        assert_order_row_has_required_contract(row)


def test_spec_summary_contains_key_order_features():
    order = generate_mock_orders(count=1, seed=42)[0]

    assert order.customer in order.spec_summary
    assert order.cpu_sku in order.spec_summary
    assert str(order.quantity) in order.spec_summary
    assert str(order.memory_gb) in order.spec_summary
    assert str(order.storage_tb) in order.spec_summary
    assert order.chassis in order.spec_summary


def test_generate_mock_order_uses_expected_order_id_format():
    rng = random.Random(42)

    order = generate_mock_order(index=3, rng=rng)

    assert order.order_id == "MOCK-0003"


def test_generated_price_and_carbon_have_reasonable_variation():
    orders = generate_mock_orders(count=DEFAULT_ORDER_COUNT, seed=42)

    prices = [order.final_price for order in orders]
    carbon_values = [order.carbon_kg for order in orders]

    assert len(set(prices)) >= MIN_UNIQUE_VALUES_FOR_VARIATION_CHECK
    assert len(set(carbon_values)) >= MIN_UNIQUE_VALUES_FOR_VARIATION_CHECK
    assert max(prices) > min(prices)
    assert max(carbon_values) > min(carbon_values)


def test_write_mock_orders_creates_csv(tmp_path):
    output_path = tmp_path / "mock_orders.csv"

    written_path = write_mock_orders(output_path=output_path, count=5, seed=42)

    assert written_path == output_path
    assert output_path.exists()


def test_write_mock_orders_preserves_required_column_order(tmp_path):
    output_path = tmp_path / "mock_orders.csv"

    write_mock_orders(output_path=output_path, count=1, seed=42)

    header = output_path.read_text(encoding="utf-8").splitlines()[0]
    assert header == ",".join(REQUIRED_COLUMNS)


def test_written_csv_has_expected_number_of_rows(tmp_path):
    output_path = tmp_path / "mock_orders.csv"

    write_mock_orders(output_path=output_path, count=5, seed=42)
    rows = read_csv_rows(output_path)

    assert len(rows) == 5


def test_written_csv_contains_required_columns(tmp_path):
    output_path = tmp_path / "mock_orders.csv"

    write_mock_orders(output_path=output_path, count=3, seed=42)

    with output_path.open("r", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        assert reader.fieldnames == list(REQUIRED_COLUMNS)


def test_written_csv_contains_parseable_numeric_values(tmp_path):
    output_path = tmp_path / "mock_orders.csv"

    write_mock_orders(output_path=output_path, count=5, seed=42)
    rows = read_csv_rows(output_path)

    for row in rows:
        assert int(row["memory_gb"]) > 0
        assert int(row["storage_tb"]) >= 0
        assert int(row["quantity"]) > 0
        assert float(row["final_price"]) > 0
        assert float(row["carbon_kg"]) > 0
        date.fromisoformat(row["delivered_at"])