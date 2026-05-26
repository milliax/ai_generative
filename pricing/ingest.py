from __future__ import annotations

import argparse
import os
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd
from sentence_transformers import SentenceTransformer


DEFAULT_CSV_PATH = Path("data/teacher_orders_for_rag.csv")
DEFAULT_PERSIST_DIR = "./chroma_db"

COLLECTION_NAME = "historical_orders"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

ID_COLUMN = "order_id"
DOCUMENT_COLUMN = "spec_summary"
REQUIRED_COLUMNS = [ID_COLUMN, DOCUMENT_COLUMN]


MetadataValue = str | int | float | bool


def get_persist_dir(persist_dir: str | Path | None = None) -> str:
    """Return the ChromaDB persistence directory.

    Priority:
    1. Explicit function argument
    2. CHROMA_PERSIST_DIR environment variable
    3. Local default ./chroma_db
    """
    if persist_dir is not None:
        return str(persist_dir)

    return os.getenv("CHROMA_PERSIST_DIR", DEFAULT_PERSIST_DIR)


def validate_csv_file_exists(csv_path: Path) -> None:
    """Raise a clear error if the input CSV file does not exist."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV file not found: {csv_path}")


def validate_required_columns(dataframe: pd.DataFrame, required_columns: list[str]) -> None:
    """Validate that the CSV contains the minimum columns required for RAG."""
    missing_columns = [column for column in required_columns if column not in dataframe.columns]

    if missing_columns:
        raise ValueError(f"Input CSV is missing required columns: {missing_columns}")


def validate_non_empty_dataframe(dataframe: pd.DataFrame) -> None:
    """Validate that the CSV contains at least one row."""
    if dataframe.empty:
        raise ValueError("Input CSV does not contain any rows.")


def validate_unique_ids(dataframe: pd.DataFrame, id_column: str = ID_COLUMN) -> None:
    """Validate that document IDs are present and unique."""
    if dataframe[id_column].isna().any():
        raise ValueError(f"Column '{id_column}' contains missing values.")

    duplicated_count = dataframe[id_column].astype(str).duplicated().sum()
    if duplicated_count > 0:
        raise ValueError(f"Column '{id_column}' contains {duplicated_count} duplicated values.")


def normalize_document_text(value: Any) -> str:
    """Normalize the document text used for embeddings."""
    if pd.isna(value):
        return ""

    return str(value).strip()


def validate_documents(documents: list[str]) -> None:
    """Validate that all embedding documents are non-empty."""
    empty_count = sum(1 for document in documents if not document)

    if empty_count > 0:
        raise ValueError(f"Column '{DOCUMENT_COLUMN}' contains {empty_count} empty documents.")


def sanitize_metadata_value(value: Any) -> MetadataValue:
    """Convert a pandas value into a ChromaDB-compatible metadata value.

    ChromaDB metadata values must be str, int, float, or bool.
    Missing values are converted to an empty string to avoid NaN serialization issues.
    """
    if pd.isna(value):
        return ""

    if isinstance(value, bool):
        return value

    if isinstance(value, Integral):
        return int(value)

    if isinstance(value, Real):
        return float(value)

    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()

    return str(value).strip()


def build_metadata_records(dataframe: pd.DataFrame) -> list[dict[str, MetadataValue]]:
    """Build metadata dictionaries for ChromaDB from all non-document columns."""
    metadata_columns = [column for column in dataframe.columns if column != DOCUMENT_COLUMN]

    return [
        {column: sanitize_metadata_value(row[column]) for column in metadata_columns}
        for _, row in dataframe.iterrows()
    ]


def load_orders_csv(csv_path: Path) -> pd.DataFrame:
    """Load and validate the RAG-ready teacher order CSV."""
    validate_csv_file_exists(csv_path)

    dataframe = pd.read_csv(csv_path, encoding="utf-8-sig")
    validate_non_empty_dataframe(dataframe)
    validate_required_columns(dataframe, REQUIRED_COLUMNS)
    validate_unique_ids(dataframe)

    return dataframe


def collection_exists(
    client: chromadb.PersistentClient,
    collection_name: str,
) -> bool:
    """Return whether a ChromaDB collection exists.

    ChromaDB versions differ in whether list_collections returns objects or names,
    so this helper supports both forms.
    """
    existing_collections = client.list_collections()

    return any(
        getattr(collection, "name", collection) == collection_name
        for collection in existing_collections
    )


def reset_collection(
    client: chromadb.PersistentClient,
    collection_name: str,
):
    """Delete and recreate a ChromaDB collection to avoid duplicate IDs."""
    if collection_exists(client, collection_name):
        client.delete_collection(collection_name)

    return client.create_collection(name=collection_name)


def embed_documents(
    documents: list[str],
    model_name: str = EMBEDDING_MODEL_NAME,
) -> list[list[float]]:
    """Create normalized embeddings for document texts."""
    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        documents,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    return embeddings.tolist()


def ingest_orders_to_chroma(
    csv_path: str | Path = DEFAULT_CSV_PATH,
    persist_dir: str | Path | None = None,
    collection_name: str = COLLECTION_NAME,
) -> int:
    """Ingest RAG-ready teacher order records into ChromaDB.

    The `spec_summary` column is embedded as the retrieval document.
    All other columns are stored as metadata.

    Args:
        csv_path: Path to the RAG-ready CSV generated by convert_teacher_excel.py.
        persist_dir: Optional ChromaDB persistence directory.
        collection_name: ChromaDB collection name.

    Returns:
        Number of ingested records.
    """
    csv_file_path = Path(csv_path)
    dataframe = load_orders_csv(csv_file_path)

    ids = dataframe[ID_COLUMN].astype(str).tolist()
    documents = dataframe[DOCUMENT_COLUMN].apply(normalize_document_text).tolist()
    validate_documents(documents)

    metadatas = build_metadata_records(dataframe)
    embeddings = embed_documents(documents)

    client = chromadb.PersistentClient(path=get_persist_dir(persist_dir))
    collection = reset_collection(client, collection_name)

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return len(ids)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Ingest teacher cable order CSV into ChromaDB.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Input CSV path. Default: {DEFAULT_CSV_PATH}",
    )
    parser.add_argument(
        "--persist-dir",
        type=Path,
        default=None,
        help="ChromaDB persist directory. Default: CHROMA_PERSIST_DIR or ./chroma_db",
    )
    parser.add_argument(
        "--collection-name",
        default=COLLECTION_NAME,
        help=f"ChromaDB collection name. Default: {COLLECTION_NAME}",
    )
    return parser.parse_args()


def main() -> None:
    """Run CSV ingestion from the command line."""
    args = parse_args()
    ingested_count = ingest_orders_to_chroma(
        csv_path=args.csv,
        persist_dir=args.persist_dir,
        collection_name=args.collection_name,
    )

    print(f"Ingested {ingested_count} records into collection '{args.collection_name}'.")


if __name__ == "__main__":
    main()
