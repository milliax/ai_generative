"""Generate mock historical order data for Pricing / RAG experiments.

This module creates deterministic mock historical server orders for the
Pricing / RAG team.

Default output:
    data/mock_orders.csv

Important:
    The generated CSV is local development data. The repository already ignores
    data/ and *.csv, so this file should not be committed.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


CsvValue = str | int | float

DEFAULT_OUTPUT_PATH = Path("data/mock_orders.csv")
DEFAULT_ORDER_COUNT = 50
DEFAULT_RANDOM_SEED = 42

REQUIRED_COLUMNS = (
    "order_id",
    "customer",
    "cpu_sku",
    "memory_gb",
    "storage_tb",
    "chassis",
    "quantity",
    "delivered_at",
    "final_price",
    "carbon_kg",
    "spec_summary",
)

CUSTOMERS = ("AWS", "Azure", "Google", "Meta", "Dell", "HPE")
CPU_SKUS = ("Xeon-8468", "Xeon-8480", "Xeon-8562Y", "Xeon-8592+", "EPYC-9654")
MEMORY_OPTIONS_GB = (128, 256, 512, 1024)
STORAGE_OPTIONS_TB = (4, 8, 16, 20, 24, 32)
CHASSIS_OPTIONS = ("1U", "2U", "4U")
QUANTITY_OPTIONS = (100, 250, 500, 1000, 1500, 2000)

BASE_DELIVERY_DATE = date(2025, 1, 1)
MAX_DELIVERY_OFFSET_DAYS = 540


@dataclass(frozen=True, slots=True)
class MockOrder:
    """One mock historical order row for Pricing / RAG experiments."""

    order_id: str
    customer: str
    cpu_sku: str
    memory_gb: int
    storage_tb: int
    chassis: str
    quantity: int
    delivered_at: str
    final_price: float
    carbon_kg: float
    spec_summary: str

    def to_csv_row(self) -> dict[str, CsvValue]:
        """Return this order as a CSV-compatible dictionary."""
        return {
            "order_id": self.order_id,
            "customer": self.customer,
            "cpu_sku": self.cpu_sku,
            "memory_gb": self.memory_gb,
            "storage_tb": self.storage_tb,
            "chassis": self.chassis,
            "quantity": self.quantity,
            "delivered_at": self.delivered_at,
            "final_price": self.final_price,
            "carbon_kg": self.carbon_kg,
            "spec_summary": self.spec_summary,
        }


def build_spec_summary(
    *,
    customer: str,
    quantity: int,
    chassis: str,
    cpu_sku: str,
    memory_gb: int,
    storage_tb: int,
) -> str:
    """Build the text field used later for embeddings and similarity search."""
    return (
        f"{customer} {quantity}x {chassis} server order with "
        f"{cpu_sku}, {memory_gb}GB memory, {storage_tb}TB storage"
    )


def estimate_final_price(
    *,
    memory_gb: int,
    storage_tb: int,
    chassis: str,
    quantity: int,
    rng: random.Random,
) -> float:
    """Estimate a mock final price.

    This is intentionally simple mock logic. It should be replaced or calibrated
    when real historical order data becomes available.
    """
    chassis_premium = {
        "1U": 150.0,
        "2U": 300.0,
        "4U": 600.0,
    }[chassis]

    base_unit_price = 2500.0
    memory_price = memory_gb * 2.5
    storage_price = storage_tb * 35.0
    unit_price = base_unit_price + memory_price + storage_price + chassis_premium
    commercial_variation = rng.uniform(0.92, 1.08)

    return round(unit_price * quantity * commercial_variation, 2)


def estimate_carbon_kg(
    *,
    memory_gb: int,
    storage_tb: int,
    chassis: str,
    quantity: int,
    rng: random.Random,
) -> float:
    """Estimate mock carbon footprint in kilograms.

    This formula is only for mock data generation. Real ESG logic should live in
    the ESG / supplier workflow later.
    """
    chassis_carbon_factor = {
        "1U": 6.0,
        "2U": 12.0,
        "4U": 25.0,
    }[chassis]

    base_carbon_per_unit = 95.0
    memory_carbon = memory_gb * 0.08
    storage_carbon = storage_tb * 1.5
    carbon_per_unit = (
        base_carbon_per_unit
        + memory_carbon
        + storage_carbon
        + chassis_carbon_factor
    )
    manufacturing_variation = rng.uniform(0.95, 1.10)

    return round(carbon_per_unit * quantity * manufacturing_variation, 2)


def generate_mock_order(index: int, rng: random.Random) -> MockOrder:
    """Generate one deterministic mock order using the provided random generator."""
    customer = rng.choice(CUSTOMERS)
    cpu_sku = rng.choice(CPU_SKUS)
    memory_gb = rng.choice(MEMORY_OPTIONS_GB)
    storage_tb = rng.choice(STORAGE_OPTIONS_TB)
    chassis = rng.choice(CHASSIS_OPTIONS)
    quantity = rng.choice(QUANTITY_OPTIONS)
    delivered_at = BASE_DELIVERY_DATE + timedelta(
        days=rng.randint(0, MAX_DELIVERY_OFFSET_DAYS)
    )

    spec_summary = build_spec_summary(
        customer=customer,
        quantity=quantity,
        chassis=chassis,
        cpu_sku=cpu_sku,
        memory_gb=memory_gb,
        storage_tb=storage_tb,
    )

    return MockOrder(
        order_id=f"MOCK-{index:04d}",
        customer=customer,
        cpu_sku=cpu_sku,
        memory_gb=memory_gb,
        storage_tb=storage_tb,
        chassis=chassis,
        quantity=quantity,
        delivered_at=delivered_at.isoformat(),
        final_price=estimate_final_price(
            memory_gb=memory_gb,
            storage_tb=storage_tb,
            chassis=chassis,
            quantity=quantity,
            rng=rng,
        ),
        carbon_kg=estimate_carbon_kg(
            memory_gb=memory_gb,
            storage_tb=storage_tb,
            chassis=chassis,
            quantity=quantity,
            rng=rng,
        ),
        spec_summary=spec_summary,
    )


def generate_mock_orders(
    count: int = DEFAULT_ORDER_COUNT,
    seed: int = DEFAULT_RANDOM_SEED,
) -> list[MockOrder]:
    """Generate deterministic mock historical orders.

    Args:
        count: Number of orders to generate.
        seed: Random seed for reproducible mock data.

    Returns:
        A list of mock historical orders.

    Raises:
        ValueError: If count is less than 1.
    """
    if count < 1:
        raise ValueError("count must be greater than or equal to 1")

    rng = random.Random(seed)
    return [generate_mock_order(index, rng) for index in range(1, count + 1)]


def write_mock_orders(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    count: int = DEFAULT_ORDER_COUNT,
    seed: int = DEFAULT_RANDOM_SEED,
) -> Path:
    """Write mock historical orders to a CSV file.

    Args:
        output_path: CSV output path.
        count: Number of orders to generate.
        seed: Random seed for reproducible mock data.

    Returns:
        The path of the written CSV file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    orders = generate_mock_orders(count=count, seed=seed)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(order.to_csv_row() for order in orders)

    return output_path


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate mock historical order data for Pricing / RAG."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="CSV output path. Default: data/mock_orders.csv",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_ORDER_COUNT,
        help="Number of mock orders to generate. Default: 50",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help="Random seed for reproducible output. Default: 42",
    )
    return parser.parse_args()


def main() -> None:
    """Run the mock data generator from the command line."""
    args = parse_args()
    output_path = write_mock_orders(
        output_path=args.output,
        count=args.count,
        seed=args.seed,
    )
    print(f"Generated mock orders: {output_path}")


if __name__ == "__main__":
    main()