import csv
from pathlib import Path

import pytest

from pricing.ingest import (
    DEFAULT_COLLECTION_NAME,
    REQUIRED_ORDER_COLUMNS,
    HistoricalOrderDataError,
    batched,
    ingest_orders_to_chroma,
    iter_historical_order_records,
    validate_historical_order_csv,
)
from pricing.retrieval import (
    compute_final_score,
    compute_structured_similarity,
    parse_query_features,
    retrieve_similar,
)


class KeywordEmbeddingProvider:
    """Deterministic embedding provider for offline tests.

    Unit tests should not download sentence-transformers models or depend on
    network access. This provider keeps retrieval tests fast and deterministic
    while still producing meaningful similarity behavior.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        normalized = text.lower()

        return [
            1.0 if "aws" in normalized else 0.0,
            1.0 if "azure" in normalized else 0.0,
            1.0 if "google" in normalized else 0.0,
            1.0 if "2u" in normalized else 0.0,
            1.0 if "4u" in normalized else 0.0,
            1.0 if "xeon-8480" in normalized else 0.0,
            1.0 if "epyc-9654" in normalized else 0.0,
            1.0 if "512gb" in normalized else 0.0,
            1.0 if "1024gb" in normalized else 0.0,
            1.0 if "20tb" in normalized else 0.0,
            1.0 if "32tb" in normalized else 0.0,
            1.0 if "1000x" in normalized else 0.0,
            1.0 if "2000x" in normalized else 0.0,
        ]


def write_orders_csv(csv_path: Path, rows: list[dict[str, str]]) -> Path:
    """Write normalized historical order rows for tests."""
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=REQUIRED_ORDER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


@pytest.fixture
def embedding_provider() -> KeywordEmbeddingProvider:
    return KeywordEmbeddingProvider()


@pytest.fixture
def sample_order_rows() -> list[dict[str, str]]:
    return [
        {
            "order_id": "HIST-001",
            "customer": "AWS",
            "cpu_sku": "Xeon-8480",
            "memory_gb": "512",
            "storage_tb": "20",
            "chassis": "2U",
            "quantity": "1000",
            "delivered_at": "2025-08-01",
            "final_price": "4200000.0",
            "carbon_kg": "180000.0",
            "spec_summary": (
                "AWS 1000x 2U server order with Xeon-8480, "
                "512GB memory, 20TB storage"
            ),
        },
        {
            "order_id": "HIST-002",
            "customer": "Google",
            "cpu_sku": "EPYC-9654",
            "memory_gb": "1024",
            "storage_tb": "32",
            "chassis": "4U",
            "quantity": "2000",
            "delivered_at": "2025-09-01",
            "final_price": "9600000.0",
            "carbon_kg": "390000.0",
            "spec_summary": (
                "Google 2000x 4U server order with EPYC-9654, "
                "1024GB memory, 32TB storage"
            ),
        },
        {
            "order_id": "HIST-003",
            "customer": "Azure",
            "cpu_sku": "Xeon-8480",
            "memory_gb": "512",
            "storage_tb": "20",
            "chassis": "2U",
            "quantity": "1000",
            "delivered_at": "2025-10-01",
            "final_price": "4300000.0",
            "carbon_kg": "185000.0",
            "spec_summary": (
                "Azure 1000x 2U server order with Xeon-8480, "
                "512GB memory, 20TB storage"
            ),
        },
    ]


def test_iter_historical_order_records_rejects_missing_file(tmp_path):
    missing_path = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        list(iter_historical_order_records(missing_path))


def test_iter_historical_order_records_rejects_missing_required_columns(tmp_path):
    csv_path = tmp_path / "bad_orders.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["order_id", "customer"])
        writer.writeheader()
        writer.writerow({"order_id": "BAD-001", "customer": "AWS"})

    with pytest.raises(HistoricalOrderDataError, match="missing required columns"):
        list(iter_historical_order_records(csv_path))


def test_iter_historical_order_records_rejects_empty_file(tmp_path):
    csv_path = tmp_path / "empty_orders.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=REQUIRED_ORDER_COLUMNS)
        writer.writeheader()

    with pytest.raises(HistoricalOrderDataError, match="contains no rows"):
        list(iter_historical_order_records(csv_path))


def test_iter_historical_order_records_rejects_invalid_numeric_value(
    tmp_path,
    sample_order_rows,
):
    csv_path = tmp_path / "bad_orders.csv"
    rows = [dict(sample_order_rows[0])]
    rows[0]["memory_gb"] = "not-a-number"

    write_orders_csv(csv_path, rows)

    with pytest.raises(HistoricalOrderDataError, match="Row 2"):
        list(iter_historical_order_records(csv_path))


def test_iter_historical_order_records_rejects_invalid_date_value(
    tmp_path,
    sample_order_rows,
):
    csv_path = tmp_path / "bad_orders.csv"
    rows = [dict(sample_order_rows[0])]
    rows[0]["delivered_at"] = "2025/08/01"

    write_orders_csv(csv_path, rows)

    with pytest.raises(HistoricalOrderDataError, match="YYYY-MM-DD"):
        list(iter_historical_order_records(csv_path))


def test_iter_historical_order_records_rejects_duplicate_order_ids(
    tmp_path,
    sample_order_rows,
):
    csv_path = tmp_path / "duplicate_orders.csv"
    rows = [dict(sample_order_rows[0]), dict(sample_order_rows[1])]
    rows[1]["order_id"] = rows[0]["order_id"]

    write_orders_csv(csv_path, rows)

    with pytest.raises(HistoricalOrderDataError, match="Duplicate order_id"):
        list(iter_historical_order_records(csv_path))


def test_iter_historical_order_records_returns_validated_records(
    tmp_path,
    sample_order_rows,
):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)

    records = list(iter_historical_order_records(csv_path))

    assert len(records) == 3
    assert records[0].order_id == "HIST-001"
    assert records[0].memory_gb == 512
    assert records[0].storage_tb == 20
    assert records[0].quantity == 1000
    assert records[0].final_price == 4200000.0
    assert records[0].carbon_kg == 180000.0


def test_validate_historical_order_csv_returns_record_count(
    tmp_path,
    sample_order_rows,
):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)

    count = validate_historical_order_csv(csv_path)

    assert count == len(sample_order_rows)


def test_historical_order_record_exposes_document_and_metadata(
    tmp_path,
    sample_order_rows,
):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)
    records = list(iter_historical_order_records(csv_path))
    record = records[0]

    metadata = record.to_metadata()

    assert record.document == record.spec_summary
    assert metadata["order_id"] == "HIST-001"
    assert metadata["customer"] == "AWS"
    assert metadata["memory_gb"] == 512
    assert metadata["final_price"] == 4200000.0
    assert "spec_summary" not in metadata


def test_batched_splits_records(sample_order_rows, tmp_path):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)
    records = tuple(iter_historical_order_records(csv_path))

    batches = list(batched(records, batch_size=2))

    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert len(batches[1]) == 1


def test_batched_rejects_invalid_batch_size(sample_order_rows, tmp_path):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)
    records = tuple(iter_historical_order_records(csv_path))

    with pytest.raises(ValueError, match="batch_size must be"):
        list(batched(records, batch_size=0))


def test_ingest_orders_to_chroma_returns_row_count(
    tmp_path,
    sample_order_rows,
    embedding_provider,
):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)
    persist_dir = tmp_path / "chroma"

    count = ingest_orders_to_chroma(
        csv_path=csv_path,
        persist_dir=persist_dir,
        embedding_provider=embedding_provider,
        batch_size=2,
    )

    assert count == len(sample_order_rows)


def test_retrieve_similar_returns_top_k_results(
    tmp_path,
    sample_order_rows,
    embedding_provider,
):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)
    persist_dir = tmp_path / "chroma"

    ingest_orders_to_chroma(
        csv_path=csv_path,
        persist_dir=persist_dir,
        embedding_provider=embedding_provider,
        batch_size=2,
    )

    results = retrieve_similar(
        query="AWS 1000x 2U server with Xeon-8480 512GB memory 20TB storage",
        k=2,
        persist_dir=persist_dir,
        embedding_provider=embedding_provider,
    )

    assert len(results) == 2
    assert results[0]["order_id"] == "HIST-001"
    assert results[0]["customer"] == "AWS"
    assert results[0]["similarity"] >= results[1]["similarity"]
    assert results[0]["final_score"] >= results[1]["final_score"]
    assert "spec_summary" in results[0]
    assert "distance" in results[0]
    assert "structured_similarity" in results[0]


@pytest.mark.parametrize("bad_query", ["", "   "])
def test_retrieve_similar_rejects_blank_query(
    tmp_path,
    bad_query,
    embedding_provider,
):
    with pytest.raises(ValueError, match="query must not be blank"):
        retrieve_similar(
            query=bad_query,
            persist_dir=tmp_path / "chroma",
            embedding_provider=embedding_provider,
        )


def test_retrieve_similar_rejects_invalid_k(tmp_path, embedding_provider):
    with pytest.raises(ValueError, match="k must be"):
        retrieve_similar(
            query="AWS 2U server",
            k=0,
            persist_dir=tmp_path / "chroma",
            embedding_provider=embedding_provider,
        )


def test_ingest_can_use_custom_collection_name(
    tmp_path,
    sample_order_rows,
    embedding_provider,
):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)
    persist_dir = tmp_path / "chroma"
    custom_collection = "teacher_orders"

    ingest_orders_to_chroma(
        csv_path=csv_path,
        persist_dir=persist_dir,
        collection_name=custom_collection,
        embedding_provider=embedding_provider,
    )

    results = retrieve_similar(
        query="Google 2000x 4U EPYC-9654 1024GB memory 32TB storage",
        k=1,
        persist_dir=persist_dir,
        collection_name=custom_collection,
        embedding_provider=embedding_provider,
    )

    assert len(results) == 1
    assert results[0]["order_id"] == "HIST-002"


def test_parse_query_features_extracts_structured_values():
    features = parse_query_features(
        "AWS 1000x 2U server with Xeon-8480 512GB memory 20TB storage"
    )

    assert features.quantity == 1000
    assert features.chassis == "2U"
    assert features.memory_gb == 512
    assert features.storage_tb == 20


def test_parse_query_features_supports_multiplication_symbol_quantity():
    features = parse_query_features(
        "AWS 1000× 2U server with Xeon-8480 512GB memory 20TB storage"
    )

    assert features.quantity == 1000


def test_parse_query_features_handles_missing_structured_values():
    features = parse_query_features("urgent AWS server quote")

    assert features.quantity is None
    assert features.chassis is None
    assert features.memory_gb is None
    assert features.storage_tb is None


def test_parse_query_features_does_not_treat_cpu_sku_suffix_as_quantity():
    features = parse_query_features("Metadata cleanup for Xeon-8480x inventory")

    assert features.quantity is None


def test_compute_structured_similarity_rewards_matching_features():
    metadata = {
        "customer": "AWS",
        "cpu_sku": "Xeon-8480",
        "memory_gb": 512,
        "storage_tb": 20,
        "chassis": "2U",
        "quantity": 1000,
    }
    query = "AWS 1000x 2U server with Xeon-8480 512GB memory 20TB storage"
    features = parse_query_features(query)

    score = compute_structured_similarity(
        query=query,
        query_features=features,
        metadata=metadata,
    )

    assert score == 1.0


def test_compute_structured_similarity_penalizes_weaker_spec_match():
    query = "AWS 1000x 2U server with Xeon-8480 512GB memory 20TB storage"
    features = parse_query_features(query)

    strong_metadata = {
        "customer": "AWS",
        "cpu_sku": "Xeon-8480",
        "memory_gb": 512,
        "storage_tb": 20,
        "chassis": "2U",
        "quantity": 1000,
    }
    weak_metadata = {
        "customer": "Google",
        "cpu_sku": "EPYC-9654",
        "memory_gb": 1024,
        "storage_tb": 32,
        "chassis": "4U",
        "quantity": 2000,
    }

    strong_score = compute_structured_similarity(
        query=query,
        query_features=features,
        metadata=strong_metadata,
    )
    weak_score = compute_structured_similarity(
        query=query,
        query_features=features,
        metadata=weak_metadata,
    )

    assert strong_score > weak_score


def test_structured_similarity_does_not_match_substrings():
    metadata = {
        "customer": "Meta",
        "cpu_sku": "Xeon-8480",
        "memory_gb": 512,
        "storage_tb": 20,
        "chassis": "2U",
        "quantity": 1000,
    }
    query = "Metadata cleanup for Xeon-8480x inventory"
    features = parse_query_features(query)

    score = compute_structured_similarity(
        query=query,
        query_features=features,
        metadata=metadata,
    )

    assert score == 0.0


def test_structured_similarity_treats_matching_zero_values_as_exact_match():
    metadata = {
        "customer": "AWS",
        "cpu_sku": "Xeon-8480",
        "memory_gb": 512,
        "storage_tb": 0,
        "chassis": "2U",
        "quantity": 1000,
    }
    query = "0TB storage"
    features = parse_query_features(query)

    score = compute_structured_similarity(
        query=query,
        query_features=features,
        metadata=metadata,
    )

    assert score == 1.0


def test_compute_final_score_combines_semantic_and_structured_scores():
    score = compute_final_score(
        semantic_similarity=0.8,
        structured_similarity=1.0,
        semantic_weight=0.65,
        structured_weight=0.35,
    )

    assert score == 0.87


def test_compute_final_score_rejects_invalid_weights():
    with pytest.raises(ValueError, match="must be greater than 0"):
        compute_final_score(
            semantic_similarity=0.8,
            structured_similarity=1.0,
            semantic_weight=0.0,
            structured_weight=0.0,
        )


def test_retrieve_similar_includes_reranking_scores(
    tmp_path,
    sample_order_rows,
    embedding_provider,
):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)
    persist_dir = tmp_path / "chroma"

    ingest_orders_to_chroma(
        csv_path=csv_path,
        persist_dir=persist_dir,
        embedding_provider=embedding_provider,
        batch_size=2,
    )

    results = retrieve_similar(
        query="AWS 1000x 2U server with Xeon-8480 512GB memory 20TB storage",
        k=2,
        persist_dir=persist_dir,
        embedding_provider=embedding_provider,
    )

    assert "similarity" in results[0]
    assert "structured_similarity" in results[0]
    assert "final_score" in results[0]
    assert results[0]["final_score"] >= results[1]["final_score"]


def test_structured_reranking_can_promote_better_spec_match(
    tmp_path,
    sample_order_rows,
    embedding_provider,
):
    csv_path = write_orders_csv(tmp_path / "orders.csv", sample_order_rows)
    persist_dir = tmp_path / "chroma"

    ingest_orders_to_chroma(
        csv_path=csv_path,
        persist_dir=persist_dir,
        embedding_provider=embedding_provider,
        batch_size=2,
    )

    results = retrieve_similar(
        query="AWS 1000x 2U server with Xeon-8480 512GB memory 20TB storage",
        k=1,
        persist_dir=persist_dir,
        embedding_provider=embedding_provider,
        semantic_weight=0.30,
        structured_weight=0.70,
    )

    assert results[0]["order_id"] == "HIST-001"
    assert results[0]["structured_similarity"] == 1.0


def test_default_collection_name_is_historical_orders():
    assert DEFAULT_COLLECTION_NAME == "historical_orders"