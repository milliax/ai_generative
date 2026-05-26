# 2026-05-26 Pricing RAG Teacher Cable Data Redo

## Participants

- CHIH YU YANG

## Topic

Redo Pricing / RAG Task 7 and Task 8 using the teacher-provided cable manufacturing scheduling dataset.

## Background

The original Pricing / RAG tasks were based on mock server order data, including CPU SKU, memory, storage, final price, and carbon fields. After receiving the teacher-provided Excel dataset, the team decided to realign Task 7 and Task 8 with the actual cable manufacturing scheduling data.

## Decisions

- Task 7 was redefined as a teacher cable data adapter.
- The adapter converts the teacher Excel file into `data/teacher_orders_for_rag.csv`.
- The generated CSV uses `spec_summary` as the embedding document field.
- Other fields are kept as ChromaDB metadata.
- Task 8 was implemented as a teacher cable RAG pipeline using ChromaDB.
- The ChromaDB collection name remains `historical_orders`.
- The pipeline does not call any LLM during ingest.
- `shared/models.py` was not modified.
- `data/`, generated CSV files, and `chroma_db/` remain ignored and are not committed.

## Implemented Files

- `scripts/convert_teacher_excel.py`
- `tests/test_convert_teacher_excel.py`
- `pricing/ingest.py`
- `pricing/retrieval.py`
- `tests/test_pricing_ingest.py`
- `tests/test_pricing_retrieval.py`

## Validation

- `python -m ruff check pricing scripts tests`
- `python -m pytest`
- End-to-end validation:
  - Teacher Excel converted to `teacher_orders_for_rag.csv`
  - 3000 records ingested into ChromaDB collection `historical_orders`
  - `retrieve_similar()` returned top-3 similar historical cable orders

## Open Issues

- Pricing Agent integration is not done yet.
- UI integration is not done yet.
- Prompt design for using retrieved cable order references is still pending.
- The original project wording still mentions server ODM/OEM and pricing; future documentation may need to clarify how the cable manufacturing dataset maps to the demo scenario.
