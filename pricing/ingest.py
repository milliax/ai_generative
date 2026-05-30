"""Ingest historical order records into ChromaDB for Pricing / RAG.

This module loads normalized historical order records from CSV, validates the
required schema, embeds the `spec_summary` field, and stores the records in a
ChromaDB collection.

The CSV path is intentionally configurable so this pipeline can ingest both:
- generated local mock data, such as data/mock_orders.csv
- teacher-provided historical order data after it has been normalized into the
  expected schema

Generated or teacher-provided CSV files must stay outside git.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol


DEFAULT_COLLECTION_NAME = "historical_orders"
DEFAULT_CHROMA_PERSIST_DIR = Path("chroma_db")
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 128

REQUIRED_ORDER_COLUMNS = (
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

MetadataValue = str | int | float | bool
OrderMetadata = dict[str, MetadataValue]
EmbeddingVector = list[float]


class HistoricalOrderDataError(ValueError):
    """Raised when historical order data is invalid or incomplete."""


class EmbeddingProvider(Protocol):
    """Protocol for embedding documents and queries."""

    def embed_documents(self, texts: list[str]) -> list[EmbeddingVector]:
        """Return one embedding vector for each document text."""

    def embed_query(self, text: str) -> EmbeddingVector:
        """Return one embedding vector for a query text."""


class SentenceTransformerEmbeddingProvider:
    """Embedding provider backed by sentence-transformers.

    The model is loaded lazily so importing this module remains lightweight.
    """

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._model = None

    def embed_documents(self, texts: list[str]) -> list[EmbeddingVector]:
        """Embed document texts."""
        return self._encode(texts)

    def embed_query(self, text: str) -> EmbeddingVector:
        """Embed one query text."""
        return self._encode([text])[0]

    def _encode(self, texts: list[str]) -> list[EmbeddingVector]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)

        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()


@dataclass(frozen=True, slots=True)
class HistoricalOrderRecord:
    """One validated historical order record for Pricing / RAG."""

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

    @classmethod
    def from_csv_row(
        cls,
        row: dict[str, str],
        row_number: int,
    ) -> HistoricalOrderRecord:
        """Create a validated record from one CSV row.

        Args:
            row: Raw CSV row.
            row_number: Human-readable CSV row number, including header row.

        Raises:
            HistoricalOrderDataError: If the row contains invalid values.
        """
        return cls(
            order_id=_require_text(row, "order_id", row_number),
            customer=_require_text(row, "customer", row_number),
            cpu_sku=_require_text(row, "cpu_sku", row_number),
            memory_gb=_parse_int(row, "memory_gb", row_number, minimum=1),
            storage_tb=_parse_int(row, "storage_tb", row_number, minimum=0),
            chassis=_require_text(row, "chassis", row_number),
            quantity=_parse_int(row, "quantity", row_number, minimum=1),
            delivered_at=_parse_date_text(row, "delivered_at", row_number),
            final_price=_parse_float(row, "final_price", row_number, minimum=0.0),
            carbon_kg=_parse_float(row, "carbon_kg", row_number, minimum=0.0),
            spec_summary=_require_text(row, "spec_summary", row_number),
        )

    @property
    def document(self) -> str:
        """Return the text to embed and store as the ChromaDB document."""
        return self.spec_summary

    def to_metadata(self) -> OrderMetadata:
        """Return ChromaDB-compatible metadata."""
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
        }


def _require_text(
    row: dict[str, str],
    column: str,
    row_number: int,
) -> str:
    value = row[column].strip()
    if not value:
        raise HistoricalOrderDataError(
            f"Row {row_number}: column '{column}' must not be empty."
        )
    return value


def _parse_int(
    row: dict[str, str],
    column: str,
    row_number: int,
    minimum: int,
) -> int:
    raw_value = row[column].strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise HistoricalOrderDataError(
            f"Row {row_number}: column '{column}' must be an integer. "
            f"Got: {raw_value!r}."
        ) from exc

    if value < minimum:
        raise HistoricalOrderDataError(
            f"Row {row_number}: column '{column}' must be >= {minimum}. "
            f"Got: {value}."
        )

    return value


def _parse_float(
    row: dict[str, str],
    column: str,
    row_number: int,
    minimum: float,
) -> float:
    raw_value = row[column].strip()
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise HistoricalOrderDataError(
            f"Row {row_number}: column '{column}' must be numeric. "
            f"Got: {raw_value!r}."
        ) from exc

    if value <= minimum:
        raise HistoricalOrderDataError(
            f"Row {row_number}: column '{column}' must be > {minimum}. "
            f"Got: {value}."
        )

    return value


def _parse_date_text(
    row: dict[str, str],
    column: str,
    row_number: int,
) -> str:
    value = _require_text(row, column, row_number)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise HistoricalOrderDataError(
            f"Row {row_number}: column '{column}' must use YYYY-MM-DD format. "
            f"Got: {value!r}."
        ) from exc

    return value


def resolve_persist_dir(persist_dir: str | Path | None = None) -> Path:
    """Resolve the ChromaDB persist directory.

    Priority:
        1. Function argument
        2. CHROMA_PERSIST_DIR environment variable
        3. Default local chroma_db directory
    """
    if persist_dir is not None:
        return Path(persist_dir)

    env_value = os.getenv("CHROMA_PERSIST_DIR")
    if env_value:
        return Path(env_value)

    return DEFAULT_CHROMA_PERSIST_DIR


def iter_historical_order_records(csv_path: str | Path) -> Iterator[HistoricalOrderRecord]:
    """Stream and validate historical order records from a CSV file.

    This function validates rows while iterating and stores only seen order IDs
    for duplicate detection. It does not keep the entire dataset in memory.

    Args:
        csv_path: Path to a normalized historical order CSV file.

    Yields:
        Validated historical order records.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        HistoricalOrderDataError: If required columns are missing, values are
            invalid, the file is empty, or duplicate order IDs exist.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Historical order CSV not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []

        missing_columns = sorted(set(REQUIRED_ORDER_COLUMNS) - set(fieldnames))
        if missing_columns:
            raise HistoricalOrderDataError(
                "Historical order CSV is missing required columns: "
                + ", ".join(missing_columns)
            )

        seen_order_ids: set[str] = set()
        row_count = 0

        for row_number, row in enumerate(reader, start=2):
            row_count += 1
            record = HistoricalOrderRecord.from_csv_row(row, row_number)

            if record.order_id in seen_order_ids:
                raise HistoricalOrderDataError(
                    f"Duplicate order_id values found: {record.order_id}"
                )

            seen_order_ids.add(record.order_id)
            yield record

        if row_count == 0:
            raise HistoricalOrderDataError(
                f"Historical order CSV contains no rows: {path}"
            )


def validate_historical_order_csv(csv_path: str | Path) -> int:
    """Validate a historical order CSV without storing all records in memory.

    Args:
        csv_path: Path to a normalized historical order CSV file.

    Returns:
        Number of valid historical order records.
    """
    count = 0
    for _record in iter_historical_order_records(csv_path):
        count += 1
    return count


def get_chroma_client(persist_dir: str | Path | None = None):
    """Create a persistent ChromaDB client."""
    import chromadb

    resolved_dir = resolve_persist_dir(persist_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(resolved_dir))


def collection_exists(client, collection_name: str) -> bool:
    """Return whether a ChromaDB collection exists."""
    collection_names = {
        collection.name if hasattr(collection, "name") else str(collection)
        for collection in client.list_collections()
    }
    return collection_name in collection_names


def reset_collection_if_exists(client, collection_name: str) -> None:
    """Delete an existing collection before re-ingesting local data."""
    if collection_exists(client, collection_name):
        client.delete_collection(name=collection_name)


def batched(
    records: Iterable[HistoricalOrderRecord],
    batch_size: int,
) -> Iterator[tuple[HistoricalOrderRecord, ...]]:
    """Yield records in fixed-size batches.

    Args:
        records: Historical order records.
        batch_size: Number of records per batch.

    Raises:
        ValueError: If batch_size is less than 1.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be greater than or equal to 1")

    batch: list[HistoricalOrderRecord] = []

    for record in records:
        batch.append(record)
        if len(batch) == batch_size:
            yield tuple(batch)
            batch.clear()

    if batch:
        yield tuple(batch)


def ingest_orders_to_chroma(
    csv_path: str | Path,
    persist_dir: str | Path | None = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_provider: EmbeddingProvider | None = None,
    reset_collection: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """Ingest historical order records into a ChromaDB collection.

    Args:
        csv_path: Path to a normalized historical order CSV file.
        persist_dir: ChromaDB persistence directory.
        collection_name: Target ChromaDB collection name.
        embedding_provider: Optional embedding provider. Defaults to
            sentence-transformers for production use.
        reset_collection: If true, delete the existing collection before ingest.
        batch_size: Number of records to write per ChromaDB batch.

    Returns:
        Number of ingested historical order records.
    """
    record_count = validate_historical_order_csv(csv_path)
    provider = embedding_provider or SentenceTransformerEmbeddingProvider()
    client = get_chroma_client(persist_dir)

    if reset_collection:
        reset_collection_if_exists(client, collection_name)

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    for record_batch in batched(
        iter_historical_order_records(csv_path),
        batch_size=batch_size,
    ):
        documents = [record.document for record in record_batch]
        embeddings = provider.embed_documents(documents)
        ids = [record.order_id for record in record_batch]
        metadatas = [record.to_metadata() for record in record_batch]

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    return record_count


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest historical order CSV data into ChromaDB."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to normalized historical order CSV data.",
    )
    parser.add_argument(
        "--persist-dir",
        type=Path,
        default=None,
        help="ChromaDB persist directory. Default: CHROMA_PERSIST_DIR or chroma_db.",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION_NAME,
        help=f"ChromaDB collection name. Default: {DEFAULT_COLLECTION_NAME}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of records per ChromaDB batch. Default: {DEFAULT_BATCH_SIZE}",
    )
    return parser.parse_args()


def main() -> None:
    """Run the ingestion workflow from the command line."""
    args = parse_args()
    ingested_count = ingest_orders_to_chroma(
        csv_path=args.csv_path,
        persist_dir=args.persist_dir,
        collection_name=args.collection,
        batch_size=args.batch_size,
    )
    print(
        f"Ingested {ingested_count} historical orders "
        f"into collection '{args.collection}'."
    )


if __name__ == "__main__":
    main()