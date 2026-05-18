# 估價 / RAG 組 工作指南

> 2 人。負責歷史訂單資料處理、RAG 檢索、估價 prompt 設計。

## 你們的定位

你們做的是**整個系統的技術深度**——Palantir 風格的「show your work」估價：給新訂單時，從歷史訂單檢索相似案例，讓 LLM 看著相似案例推估價格、交期、碳排，並附上參考案例。

Demo 時這是最讓老師「哇」的部分。

## 你們可以依賴的東西（PM 已交付）

```python
from shared.models import OrderSpec, CoordinationPlan
from shared.llm_client import call_llm
```

ChromaDB、sentence-transformers、pandas 都已經在 `requirements.txt`。

## 分工建議

| 人 | Task | 檔案 |
|---|---|---|
| **A** | Task 7: Mock data generator + 接老師資料 | `scripts/generate_mock_orders.py`、`data/` 整理 |
| **B** | Task 8: RAG ingest + retrieval | `pricing/ingest.py`、`pricing/retrieval.py` |

依賴：A 先做完 Task 7 才能有東西餵 B 的 RAG。但 B 可以在等的時候先寫 ingest 程式碼（用空 list 測 schema 也行）。

## 你們的關鍵任務：跟老師談資料

**這是最大的風險變數**。請主動聯絡老師：

- 老師會給多少筆歷史訂單？什麼欄位？格式（CSV / Excel / DB dump）？
- 有沒有 NDA / 資料敏感性的限制？
- 什麼時候會給？

PM 已經知道這事，但你們是實際要用資料的人，**5/20 前要拿到答案**。如果老師資料不全，你們補 mock data；如果完全沒有，就純 mock。

**重要：** 等資料到了，把欄位 schema 跟 PM 對齊，可能要更新 `OrderSpec` 或加新的歷史訂單 schema。

## Task 7: Mock Data Generator

**檔案：** `scripts/generate_mock_orders.py`

產生 50 筆假歷史訂單到 `data/mock_orders.csv`，欄位設計**要跟老師資料對齊**（如果還沒拿到，先用下面這套）。

### 必要欄位

| 欄位 | 型別 | 範例 |
|---|---|---|
| `order_id` | str | `"HIST-0001"` |
| `customer` | str | `"AWS"` |
| `cpu_sku` | str | `"Xeon-9654"` |
| `memory_gb` | int | `512` |
| `storage_tb` | int | `20` |
| `chassis` | str | `"2U"` |
| `quantity` | int | `1000` |
| `delivered_at` | date | `"2025-08-15"` |
| `final_price` | float | `51200000.00` |
| `carbon_kg` | float | `120000.50` |
| `spec_summary` | str | `"AWS 1000× 2U Xeon-9654 512GB/20TB"` ← embedding 用這欄 |

完整 generator 程式在 [plan Task 7](../superpowers/plans/2026-05-18-w1-scaffold.md#task-7-mock-data-generator)。

### 注意事項

- `data/` 在 `.gitignore` 內，**生出來的 CSV 不會被 commit**（這是對的，避免 repo 肥大 + 真實資料外洩）
- 用 `random.Random(seed=42)` 讓 mock 可重現
- 價格 / 碳排不要全部用同一個公式——加點隨機 noise，RAG 才會學到「相似但不同」

## Task 8: ChromaDB Ingest + Retrieval

**檔案：** `pricing/ingest.py`、`pricing/retrieval.py`

### Ingest（`pricing/ingest.py`）

```python
def ingest_orders_to_chroma(csv_path, persist_dir=None) -> int:
    """讀 CSV → embedding (spec_summary) → ChromaDB。回傳筆數。"""
```

- Embedding model：`sentence-transformers/all-MiniLM-L6-v2`（小、本地、零 API 成本）
- Collection 名稱：`"historical_orders"`
- Embedding 用 `spec_summary` 欄位；其他欄位放 `metadata`
- 重跑時先 `delete_collection` 再 `create_collection`（避免重複）

### Retrieval（`pricing/retrieval.py`）

```python
def retrieve_similar(query: str, k: int = 5, persist_dir=None) -> list[dict]:
    """依規格摘要檢索 top-K 相似訂單。回傳 metadata + similarity。"""
```

- ChromaDB 的 `query()` 回 `distances`，要轉成 `similarity = 1 - distance`
- 回的 list 每個 dict 包含所有 metadata 欄位 + `similarity`

完整實作在 [plan Task 8](../superpowers/plans/2026-05-18-w1-scaffold.md#task-8-rag-ingest--retrieval-stub)。

### 第一次跑 sentence-transformers 會很慢

下載 ~90MB 模型。一次後就快了。**第一次跑測試前先單獨跑一次 `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"`** 把模型下載好，否則 pytest 會卡很久。

## W2 才要做的（不要在 W1 做）

- 真的把 retrieval 串到 PricingAgent
- 設計估價 prompt 結構：
  ```
  你是資深業務。下面是 {k} 筆相似歷史訂單：
  {reference_orders}

  要估價的新訂單：
  {new_spec}

  請推估：價格、信心區間、交期。說明哪幾筆最像、差異對價格的影響。
  ```
- A/B 測試 prompt（同一個輸入跑 3 個 prompt 變體，看哪個輸出最穩）
- 接老師真實資料

## 規則

1. **`data/` 永遠不 commit**——`.gitignore` 已擋
2. **ChromaDB 持久化路徑用 env**：`os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")`
3. **不要在 ingest 裡叫 LLM**——embedding 用 sentence-transformers，零 LLM 成本
4. **不要改 `shared/models.py`**——RAG 結果用 `dict[str, Any]` 回傳，組成 `CoordinationPlan.reference_orders`
5. **測試一定要用 `tmp_path` fixture**——不要污染真實的 `./chroma_db/`

## 你們可能踩的雷

| 雷 | 怎麼避 |
|---|---|
| Embedding 第一次很慢 → 測試 timeout | 先單獨下載模型，再跑 pytest |
| ChromaDB collection 重複 add 同一個 id | Ingest 開頭先 `delete_collection` |
| Distance ↔ similarity 搞錯方向 | `similarity = 1 - distance`，並 clamp 到 [0, 1] |
| Top-K 太大（K=20）導致 LLM context 爆 | W2 預設 K=5，最多 K=10 |
| 真實老師資料欄位跟 mock 不合 | 5/20 前確認，必要時修 schema |

## W1 驗收

- [ ] `pytest tests/test_mock_data.py -v` 全綠
- [ ] `pytest tests/test_pricing_rag.py -v` 全綠
- [ ] `python scripts/generate_mock_orders.py` 產出 50 筆 csv
- [ ] `python -c "from pricing.retrieval import retrieve_similar; print(retrieve_similar('AWS 1000× 2U Xeon 512GB/20TB', k=3))"` 回 3 筆結果

## 連結

- Plan 細節：[`docs/superpowers/plans/2026-05-18-w1-scaffold.md`](../superpowers/plans/2026-05-18-w1-scaffold.md)（Task 7、8）
- 系統設計：[`docs/superpowers/specs/2026-05-18-multi-agent-design.md`](../superpowers/specs/2026-05-18-multi-agent-design.md)（特別看「Pricing Agent 細節」）
- Schemas：[`shared/models.py`](../../shared/models.py)
