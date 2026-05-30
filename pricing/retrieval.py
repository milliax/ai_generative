"""Retrieve and rerank similar historical orders for Pricing / RAG."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pricing.ingest import (
    DEFAULT_COLLECTION_NAME,
    EmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    get_chroma_client,
)


DEFAULT_SEMANTIC_WEIGHT = 0.65
DEFAULT_STRUCTURED_WEIGHT = 0.35
DEFAULT_RERANK_CANDIDATE_MULTIPLIER = 4
DEFAULT_MIN_RERANK_CANDIDATES = 20


@dataclass(frozen=True, slots=True)
class QueryFeatures:
    """Structured features parsed from a free-form order query."""

    quantity: int | None = None
    chassis: str | None = None
    memory_gb: int | None = None
    storage_tb: int | None = None


@dataclass(frozen=True, slots=True)
class SimilarOrderResult:
    """One similar historical order returned from retrieval."""

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
    distance: float
    similarity: float
    structured_similarity: float
    final_score: float

    @classmethod
    def from_chroma_result(
        cls,
        *,
        document: str,
        metadata: dict[str, Any],
        distance: float,
        query: str,
        query_features: QueryFeatures,
        semantic_weight: float,
        structured_weight: float,
    ) -> SimilarOrderResult:
        """Create a retrieval result from one ChromaDB result item."""
        normalized_distance = round(float(distance), 6)
        semantic_similarity = distance_to_similarity(normalized_distance)
        structured_similarity = compute_structured_similarity(
            query=query,
            query_features=query_features,
            metadata=metadata,
        )
        final_score = compute_final_score(
            semantic_similarity=semantic_similarity,
            structured_similarity=structured_similarity,
            semantic_weight=semantic_weight,
            structured_weight=structured_weight,
        )

        return cls(
            order_id=str(metadata["order_id"]),
            customer=str(metadata["customer"]),
            cpu_sku=str(metadata["cpu_sku"]),
            memory_gb=int(metadata["memory_gb"]),
            storage_tb=int(metadata["storage_tb"]),
            chassis=str(metadata["chassis"]),
            quantity=int(metadata["quantity"]),
            delivered_at=str(metadata["delivered_at"]),
            final_price=float(metadata["final_price"]),
            carbon_kg=float(metadata["carbon_kg"]),
            spec_summary=document,
            distance=normalized_distance,
            similarity=semantic_similarity,
            structured_similarity=structured_similarity,
            final_score=final_score,
        )

    def to_dict(self) -> dict[str, str | int | float]:
        """Return this retrieval result as a plain dictionary."""
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
            "distance": self.distance,
            "similarity": self.similarity,
            "structured_similarity": self.structured_similarity,
            "final_score": self.final_score,
        }


def distance_to_similarity(distance: float) -> float:
    """Convert Chroma cosine distance into a similarity-style score."""
    return round(max(0.0, min(1.0, 1.0 - distance)), 6)


def parse_query_features(query: str) -> QueryFeatures:
    """Extract structured order features from a free-form query."""
    normalized_query = query.lower()

    return QueryFeatures(
        quantity=_parse_quantity(normalized_query),
        chassis=_parse_chassis(normalized_query),
        memory_gb=_parse_capacity(normalized_query, unit="gb"),
        storage_tb=_parse_capacity(normalized_query, unit="tb"),
    )


def _parse_quantity(normalized_query: str) -> int | None:
    """Parse order quantity such as '1000x' or '1000×'.

    This intentionally avoids parsing CPU/SKU fragments such as 'Xeon-8480x'
    as an order quantity.
    """
    match = re.search(
        r"(?<![A-Za-z0-9-])(\d+)\s*[x×](?![A-Za-z0-9])",
        normalized_query,
    )
    if match:
        return int(match.group(1))
    return None


def _parse_chassis(normalized_query: str) -> str | None:
    """Parse chassis values such as 1U, 2U, or 4U."""
    match = re.search(r"\b([124])u\b", normalized_query)
    if match:
        return f"{match.group(1).upper()}U"
    return None


def _parse_capacity(normalized_query: str, unit: str) -> int | None:
    """Parse capacity values such as 512GB or 20TB."""
    match = re.search(rf"\b(\d+)\s*{unit}\b", normalized_query)
    if match:
        return int(match.group(1))
    return None


def contains_exact_term(normalized_text: str, term: str) -> bool:
    """Return whether a term appears as an exact token-like match.

    This avoids false positives such as customer "Meta" matching "Metadata".
    It also supports SKU values that contain symbols, such as "Xeon-8592+".
    """
    normalized_term = term.strip().lower()
    if not normalized_term:
        return False

    pattern = rf"(?<![A-Za-z0-9]){re.escape(normalized_term)}(?![A-Za-z0-9])"
    return re.search(pattern, normalized_text) is not None


def compute_structured_similarity(
    *,
    query: str,
    query_features: QueryFeatures,
    metadata: dict[str, Any],
) -> float:
    """Compute structured similarity between query features and order metadata.

    The score is normalized by the features available in the query. Missing
    query features are ignored instead of being treated as mismatches.
    """
    normalized_query = query.lower()
    weighted_scores: list[tuple[float, float]] = []

    customer = str(metadata["customer"])
    if contains_exact_term(normalized_query, customer):
        weighted_scores.append((0.18, 1.0))

    cpu_sku = str(metadata["cpu_sku"])
    if contains_exact_term(normalized_query, cpu_sku):
        weighted_scores.append((0.22, 1.0))

    if query_features.chassis is not None:
        score = _exact_match_score(
            query_value=query_features.chassis,
            candidate_value=str(metadata["chassis"]),
        )
        weighted_scores.append((0.18, score))

    if query_features.memory_gb is not None:
        score = _numeric_closeness_score(
            query_value=query_features.memory_gb,
            candidate_value=int(metadata["memory_gb"]),
        )
        weighted_scores.append((0.16, score))

    if query_features.storage_tb is not None:
        score = _numeric_closeness_score(
            query_value=query_features.storage_tb,
            candidate_value=int(metadata["storage_tb"]),
        )
        weighted_scores.append((0.14, score))

    if query_features.quantity is not None:
        score = _numeric_closeness_score(
            query_value=query_features.quantity,
            candidate_value=int(metadata["quantity"]),
        )
        weighted_scores.append((0.12, score))

    if not weighted_scores:
        return 0.0

    total_weight = sum(weight for weight, _score in weighted_scores)
    weighted_sum = sum(weight * score for weight, score in weighted_scores)

    return round(weighted_sum / total_weight, 6)


def _exact_match_score(query_value: str, candidate_value: str) -> float:
    """Return 1.0 only for exact categorical matches."""
    return 1.0 if query_value.lower() == candidate_value.lower() else 0.0


def _numeric_closeness_score(query_value: int, candidate_value: int) -> float:
    """Return a bounded numeric closeness score.

    Equal zero values are treated as a perfect match. Otherwise, the score is
    the ratio between the smaller and larger value.
    """
    larger = max(query_value, candidate_value)
    smaller = min(query_value, candidate_value)

    if larger == 0:
        return 1.0

    return round(smaller / larger, 6)


def compute_final_score(
    *,
    semantic_similarity: float,
    structured_similarity: float,
    semantic_weight: float,
    structured_weight: float,
) -> float:
    """Combine semantic and structured similarity into a reranking score."""
    weight_sum = semantic_weight + structured_weight
    if weight_sum <= 0:
        raise ValueError("semantic_weight + structured_weight must be greater than 0")

    normalized_semantic_weight = semantic_weight / weight_sum
    normalized_structured_weight = structured_weight / weight_sum

    score = (
        normalized_semantic_weight * semantic_similarity
        + normalized_structured_weight * structured_similarity
    )
    return round(score, 6)


def _validate_query(query: str) -> str:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be blank")
    return normalized_query


def _validate_top_k(k: int) -> int:
    if k < 1:
        raise ValueError("k must be greater than or equal to 1")
    return k


def _candidate_count(k: int) -> int:
    return max(k * DEFAULT_RERANK_CANDIDATE_MULTIPLIER, DEFAULT_MIN_RERANK_CANDIDATES)


def retrieve_similar(
    query: str,
    k: int = 5,
    persist_dir: str | Path | None = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_provider: EmbeddingProvider | None = None,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
    structured_weight: float = DEFAULT_STRUCTURED_WEIGHT,
) -> list[dict[str, str | int | float]]:
    """Retrieve and rerank top-k similar historical orders.

    Args:
        query: New order specification text.
        k: Number of similar historical orders to return.
        persist_dir: ChromaDB persistence directory.
        collection_name: Source ChromaDB collection name.
        embedding_provider: Optional embedding provider. Defaults to
            sentence-transformers for production use.
        semantic_weight: Weight for vector similarity.
        structured_weight: Weight for structured feature similarity.

    Returns:
        A list of dictionaries containing normalized historical order metadata,
        spec_summary, distance, similarity, structured_similarity, and final_score.

    Raises:
        ValueError: If query is blank, k is less than 1, or score weights are invalid.
    """
    normalized_query = _validate_query(query)
    top_k = _validate_top_k(k)
    query_features = parse_query_features(normalized_query)

    provider = embedding_provider or SentenceTransformerEmbeddingProvider()
    query_embedding = provider.embed_query(normalized_query)

    client = get_chroma_client(persist_dir)
    collection = client.get_collection(name=collection_name)

    raw_result = collection.query(
        query_embeddings=[query_embedding],
        n_results=_candidate_count(top_k),
        include=["documents", "metadatas", "distances"],
    )

    results = _format_chroma_results(
        raw_result=raw_result,
        query=normalized_query,
        query_features=query_features,
        semantic_weight=semantic_weight,
        structured_weight=structured_weight,
    )
    reranked_results = sorted(
        results,
        key=lambda result: result.final_score,
        reverse=True,
    )

    return [result.to_dict() for result in reranked_results[:top_k]]


def _format_chroma_results(
    *,
    raw_result: dict[str, Any],
    query: str,
    query_features: QueryFeatures,
    semantic_weight: float,
    structured_weight: float,
) -> list[SimilarOrderResult]:
    documents = raw_result.get("documents", [[]])[0]
    metadatas = raw_result.get("metadatas", [[]])[0]
    distances = raw_result.get("distances", [[]])[0]

    return [
        SimilarOrderResult.from_chroma_result(
            document=document,
            metadata=metadata,
            distance=distance,
            query=query,
            query_features=query_features,
            semantic_weight=semantic_weight,
            structured_weight=structured_weight,
        )
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Retrieve similar historical orders from ChromaDB."
    )
    parser.add_argument(
        "query",
        help="New order specification text.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of similar orders to retrieve. Default: 5",
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
    return parser.parse_args()


def main() -> None:
    """Run retrieval from the command line."""
    args = parse_args()
    results = retrieve_similar(
        query=args.query,
        k=args.top_k,
        persist_dir=args.persist_dir,
        collection_name=args.collection,
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()