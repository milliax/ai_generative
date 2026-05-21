import csv

import pytest

from scripts.generate_mock_orders import (
    REQUIRED_COLUMNS,
    generate_mock_order,
    generate_mock_orders,
    write_mock_orders,
)


def test_generate_mock_orders_default_count():
    orders = generate_mock_orders()

    assert len(orders) == 50


def test_generate_mock_orders_custom_count():
    orders = generate_mock_orders(count=7)

    assert len(orders) == 7


def test_generate_mock_orders_rejects_invalid_count():
    with pytest.raises(ValueError, match="count must be"):
        generate_mock_orders(count=0)


def test_generate_mock_orders_are_reproducible_with_same_seed():
    first_run = [order.to_csv_row() for order in generate_mock_orders(seed=123)]
    second_run = [order.to_csv_row() for order in generate_mock_orders(seed=123)]

    assert first_run == second_run


def test_generate_mock_order_contains_required_columns():
    order = generate_mock_orders(count=1)[0]
    row = order.to_csv_row()

    assert set(row) == set(REQUIRED_COLUMNS)


def test_mock_order_values_are_valid():
    orders = generate_mock_orders(count=10)

    for order in orders:
        row = order.to_csv_row()

        assert row["order_id"].startswith("MOCK-")
        assert row["customer"]
        assert row["cpu_sku"]
        assert row["memory_gb"] > 0
        assert row["storage_tb"] >= 0
        assert row["chassis"] in {"1U", "2U", "4U"}
        assert row["quantity"] > 0
        assert row["delivered_at"]
        assert row["final_price"] > 0
        assert row["carbon_kg"] > 0
        assert row["spec_summary"]


def test_spec_summary_contains_key_order_features():
    order = generate_mock_orders(count=1, seed=42)[0]

    assert order.customer in order.spec_summary
    assert order.cpu_sku in order.spec_summary
    assert str(order.quantity) in order.spec_summary
    assert str(order.memory_gb) in order.spec_summary
    assert str(order.storage_tb) in order.spec_summary
    assert order.chassis in order.spec_summary


def test_generate_mock_order_uses_expected_order_id_format():
    import random

    rng = random.Random(42)
    order = generate_mock_order(index=3, rng=rng)

    assert order.order_id == "MOCK-0003"


def test_write_mock_orders_creates_csv(tmp_path):
    output_path = tmp_path / "mock_orders.csv"

    written_path = write_mock_orders(output_path=output_path, count=5)

    assert written_path == output_path
    assert output_path.exists()

    with output_path.open("r", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    assert reader.fieldnames == list(REQUIRED_COLUMNS)
    assert len(rows) == 5


def test_write_mock_orders_preserves_required_column_order(tmp_path):
    output_path = tmp_path / "mock_orders.csv"

    write_mock_orders(output_path=output_path, count=1)

    header = output_path.read_text(encoding="utf-8").splitlines()[0]
    assert header == ",".join(REQUIRED_COLUMNS)