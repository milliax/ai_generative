from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from pricing.ingest import (
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    get_persist_dir,
)


def validate_query(query: str) -> None:
    """Validate user query before embedding."""
    if not query or not query.strip():
        raise ValueError("query must not be empty.")


def validate_top_k(k: int) -> None:
    """Validate top-k retrieval count."""
    if k < 1:
        raise ValueError("k must be greater than or equal to 1.")


def clamp_similarity(value: float) -> float:
    """Clamp similarity score to the inclusive [0, 1] range."""
    return max(0.0, min(1.0, value))


def embed_query(
    query: str,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> list[float]:
    """Create a normalized embedding for one query string."""
    model = SentenceTransformer(model_name)
    embedding = model.encode(
        [query],
        normalize_embeddings=True,
    )

    return embedding.tolist()[0]


def get_collection(
    persist_dir: str | Path | None = None,
    collection_name: str = COLLECTION_NAME,
):
    """Load an existing ChromaDB collection."""
    client = chromadb.PersistentClient(path=get_persist_dir(persist_dir))
    return client.get_collection(name=collection_name)


def build_retrieval_result(
    *,
    document: str,
    metadata: dict[str, Any],
    distance: float,
) -> dict[str, Any]:
    """Build one user-facing retrieval result.

    ChromaDB returns distances, where lower is better. For this project,
    expose a bounded similarity score so downstream agents can rank results
    more intuitively.
    """
    similarity = clamp_similarity(1.0 - float(distance))

    result = dict(metadata)
    result["matched_summary"] = document
    result["similarity"] = round(similarity, 4)

    return result


def retrieve_similar(
    query: str,
    k: int = 5,
    persist_dir: str | Path | None = None,
    collection_name: str = COLLECTION_NAME,
) -> list[dict[str, Any]]:
    """Retrieve top-k similar historical orders from ChromaDB.

    Args:
        query: New order description or spec summary.
        k: Number of similar records to return.
        persist_dir: Optional ChromaDB persistence directory.
        collection_name: ChromaDB collection name.

    Returns:
        A list of metadata dictionaries with matched_summary and similarity.
    """
    validate_query(query)
    validate_top_k(k)

    collection = get_collection(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )
    query_embedding = embed_query(query)

    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    documents = raw_results.get("documents", [[]])[0]
    metadatas = raw_results.get("metadatas", [[]])[0]
    distances = raw_results.get("distances", [[]])[0]

    return [
        build_retrieval_result(
            document=document,
            metadata=metadata,
            distance=distance,
        )
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Retrieve similar teacher cable orders from ChromaDB."
    )
    parser.add_argument("query", help="New order text or spec summary.")
    parser.add_argument("--k", type=int, default=5, help="Number of records to return.")
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
    """Run retrieval from the command line."""
    args = parse_args()
    results = retrieve_similar(
        query=args.query,
        k=args.k,
        persist_dir=args.persist_dir,
        collection_name=args.collection_name,
    )

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
