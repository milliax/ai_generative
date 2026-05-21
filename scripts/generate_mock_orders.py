"""Generate mock historical order data for the Pricing / RAG pipeline.

This module creates deterministic historical order records for local
development, integration testing, and RAG pipeline validation.

Default output:
    data/mock_orders.csv

Important:
    The generated CSV is local development data. The repository ignores data/
    and *.csv, so generated order files should not be committed.
"""

from __future__ import annotations

import argparse
import csv
import math
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
class CustomerProfile:
    """Commercial and logistics profile for a customer segment."""

    price_factor: float
    carbon_factor: float


@dataclass(frozen=True, slots=True)
class CpuProfile:
    """Relative cost and carbon profile for a CPU SKU."""

    price_factor: float
    carbon_factor: float
    supply_risk_factor: float


@dataclass(frozen=True, slots=True)
class ChassisProfile:
    """Mechanical and integration profile for a chassis type."""

    price_premium: float
    carbon_addition_kg: float
    integration_factor: float


@dataclass(frozen=True, slots=True)
class MockOrder:
    """One generated historical order record."""

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


CUSTOMER_PROFILES = {
    "AWS": CustomerProfile(price_factor=0.94, carbon_factor=0.97),
    "Azure": CustomerProfile(price_factor=0.95, carbon_factor=0.98),
    "Google": CustomerProfile(price_factor=0.96, carbon_factor=0.96),
    "Meta": CustomerProfile(price_factor=0.97, carbon_factor=0.99),
    "Dell": CustomerProfile(price_factor=1.00, carbon_factor=1.02),
    "HPE": CustomerProfile(price_factor=1.02, carbon_factor=1.03),
}

CPU_PROFILES = {
    "Xeon-8468": CpuProfile(price_factor=1.00, carbon_factor=1.00, supply_risk_factor=1.00),
    "Xeon-8480": CpuProfile(price_factor=1.07, carbon_factor=1.04, supply_risk_factor=1.01),
    "Xeon-8562Y": CpuProfile(price_factor=1.12, carbon_factor=1.08, supply_risk_factor=1.03),
    "Xeon-8592+": CpuProfile(price_factor=1.22, carbon_factor=1.15, supply_risk_factor=1.06),
    "EPYC-9654": CpuProfile(price_factor=1.18, carbon_factor=1.12, supply_risk_factor=1.05),
}

CHASSIS_PROFILES = {
    "1U": ChassisProfile(price_premium=150.0, carbon_addition_kg=6.0, integration_factor=1.00),
    "2U": ChassisProfile(price_premium=320.0, carbon_addition_kg=14.0, integration_factor=1.03),
    "4U": ChassisProfile(price_premium=720.0, carbon_addition_kg=30.0, integration_factor=1.08),
}


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a numeric value to an inclusive range."""
    return max(lower, min(value, upper))


def months_since_base(delivered_at: date) -> int:
    """Return the number of months between the base date and delivery date."""
    return (
        (delivered_at.year - BASE_DELIVERY_DATE.year) * 12
        + delivered_at.month
        - BASE_DELIVERY_DATE.month
    )


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


def volume_price_factor(quantity: int) -> float:
    """Return a tiered commercial discount factor for order volume."""
    if quantity >= 2000:
        return 0.88
    if quantity >= 1500:
        return 0.90
    if quantity >= 1000:
        return 0.93
    if quantity >= 500:
        return 0.96
    if quantity >= 250:
        return 0.98
    return 1.00


def production_efficiency_factor(quantity: int) -> float:
    """Return the carbon efficiency factor gained from larger batches."""
    if quantity >= 2000:
        return 0.92
    if quantity >= 1500:
        return 0.94
    if quantity >= 1000:
        return 0.96
    if quantity >= 500:
        return 0.98
    return 1.00


def market_price_factor(delivered_at: date) -> float:
    """Return a date-based market factor.

    This models broad market movement using mild inflation and a seasonal cycle.
    It gives the generated dataset time-based structure without relying only on
    random noise.
    """
    elapsed_months = months_since_base(delivered_at)
    inflation = 1.0 + 0.0035 * elapsed_months
    procurement_cycle = 1.0 + 0.025 * math.sin(elapsed_months / 3.0)
    return inflation * procurement_cycle


def supply_chain_factor(
    *,
    cpu_sku: str,
    delivered_at: date,
    rng: random.Random,
) -> float:
    """Return a supply-chain pressure factor for price generation."""
    cpu_profile = CPU_PROFILES[cpu_sku]
    quarter_index = (delivered_at.month - 1) // 3
    quarter_pressure = 1.0 + 0.015 * quarter_index
    residual_pressure = clamp(rng.gauss(mu=1.0, sigma=0.025), 0.94, 1.08)

    return cpu_profile.supply_risk_factor * quarter_pressure * residual_pressure


def configuration_complexity_factor(
    *,
    memory_gb: int,
    storage_tb: int,
    chassis: str,
) -> float:
    """Return a complexity factor for dense or validation-heavy configurations."""
    factor = CHASSIS_PROFILES[chassis].integration_factor

    if memory_gb >= 1024:
        factor += 0.045
    elif memory_gb >= 512:
        factor += 0.025

    if storage_tb >= 24:
        factor += 0.030
    elif storage_tb >= 16:
        factor += 0.015

    if chassis == "1U" and memory_gb >= 512:
        factor += 0.035

    if chassis == "4U" and storage_tb >= 24:
        factor += 0.020

    return factor


def commercial_residual_factor(rng: random.Random) -> float:
    """Return bounded commercial variation for quote-level differences."""
    return clamp(rng.gauss(mu=1.0, sigma=0.035), 0.90, 1.11)


def manufacturing_residual_factor(rng: random.Random) -> float:
    """Return bounded manufacturing variation for carbon footprint differences."""
    return clamp(rng.gauss(mu=1.0, sigma=0.030), 0.92, 1.10)


def logistics_carbon_factor(customer: str, rng: random.Random) -> float:
    """Return a customer-specific logistics and routing carbon factor."""
    customer_profile = CUSTOMER_PROFILES[customer]
    routing_residual = clamp(rng.gauss(mu=1.0, sigma=0.025), 0.94, 1.07)

    return customer_profile.carbon_factor * routing_residual


def grid_carbon_factor(delivered_at: date) -> float:
    """Return a time-based grid carbon factor.

    This models gradual grid improvement and mild seasonal effects.
    """
    elapsed_months = months_since_base(delivered_at)
    improvement = 1.0 - 0.0018 * elapsed_months
    seasonal_effect = 1.0 + 0.015 * math.cos(delivered_at.month / 12.0 * 2.0 * math.pi)

    return clamp(improvement * seasonal_effect, 0.93, 1.04)


def estimate_final_price(
    *,
    customer: str,
    cpu_sku: str,
    memory_gb: int,
    storage_tb: int,
    chassis: str,
    quantity: int,
    delivered_at: date,
    rng: random.Random,
) -> float:
    """Estimate a structured mock final price.

    The value combines configuration cost, customer commercial profile, volume
    discounts, delivery-date market movement, supply-chain pressure, and a
    bounded residual factor.
    """
    customer_profile = CUSTOMER_PROFILES[customer]
    cpu_profile = CPU_PROFILES[cpu_sku]
    chassis_profile = CHASSIS_PROFILES[chassis]

    base_unit_price = 2300.0
    cpu_price = 780.0 * cpu_profile.price_factor
    memory_price = 18.0 * (memory_gb**0.82)
    storage_price = 115.0 * (storage_tb**0.74)

    unit_price = (
        base_unit_price
        + cpu_price
        + memory_price
        + storage_price
        + chassis_profile.price_premium
    )
    unit_price *= configuration_complexity_factor(
        memory_gb=memory_gb,
        storage_tb=storage_tb,
        chassis=chassis,
    )

    structured_factor = (
        customer_profile.price_factor
        * volume_price_factor(quantity)
        * market_price_factor(delivered_at)
        * supply_chain_factor(cpu_sku=cpu_sku, delivered_at=delivered_at, rng=rng)
        * commercial_residual_factor(rng)
    )

    return round(unit_price * quantity * structured_factor, 2)


def estimate_carbon_kg(
    *,
    customer: str,
    cpu_sku: str,
    memory_gb: int,
    storage_tb: int,
    chassis: str,
    quantity: int,
    delivered_at: date,
    rng: random.Random,
) -> float:
    """Estimate a structured mock carbon footprint in kilograms.

    The value combines component footprint, chassis footprint, batch efficiency,
    logistics profile, grid effects, and bounded manufacturing variation.
    """
    cpu_profile = CPU_PROFILES[cpu_sku]
    chassis_profile = CHASSIS_PROFILES[chassis]

    base_carbon_per_unit = 78.0
    cpu_carbon = 42.0 * cpu_profile.carbon_factor
    memory_carbon = 0.095 * memory_gb
    storage_carbon = 2.1 * storage_tb

    carbon_per_unit = (
        base_carbon_per_unit
        + cpu_carbon
        + memory_carbon
        + storage_carbon
        + chassis_profile.carbon_addition_kg
    )

    structured_factor = (
        production_efficiency_factor(quantity)
        * logistics_carbon_factor(customer, rng)
        * grid_carbon_factor(delivered_at)
        * manufacturing_residual_factor(rng)
    )

    return round(carbon_per_unit * quantity * structured_factor, 2)


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
            customer=customer,
            cpu_sku=cpu_sku,
            memory_gb=memory_gb,
            storage_tb=storage_tb,
            chassis=chassis,
            quantity=quantity,
            delivered_at=delivered_at,
            rng=rng,
        ),
        carbon_kg=estimate_carbon_kg(
            customer=customer,
            cpu_sku=cpu_sku,
            memory_gb=memory_gb,
            storage_tb=storage_tb,
            chassis=chassis,
            quantity=quantity,
            delivered_at=delivered_at,
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
        A list of generated historical orders.

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
    """Write generated historical orders to a CSV file.

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
        description="Generate historical mock order data for Pricing / RAG."
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