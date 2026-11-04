# PaySim data dictionary

The canonical PaySim CSV commonly includes `step`, `type`, `amount`, `nameOrig`, `oldbalanceOrg`, `newbalanceOrig`, `nameDest`, `oldbalanceDest`, `newbalanceDest`, `isFraud`, and `isFlaggedFraud`. This project adds `txn_id`, `produced_at`, and a computed experiment `variant` during ingestion.

| Field | Meaning | Handling |
|---|---|---|
| `step` | Simulated hour index | Numeric feature |
| `type` | PAYMENT, TRANSFER, CASH_OUT, CASH_IN, DEBIT | Categorical |
| `amount` | Transaction amount | Validate non-negative |
| `nameOrig` | Sender account identifier | Sensitive; do not expose to analysts |
| `nameDest` | Receiver account identifier | Sensitive; do not expose to analysts |
| `oldbalanceOrg`, `newbalanceOrig` | Sender balance before/after | Financial data |
| `oldbalanceDest`, `newbalanceDest` | Receiver balance before/after | Financial data |
| `isFraud` | Synthetic ground-truth label | Evaluation only; never a live feature |
| `isFlaggedFraud` | Dataset's own flag | Baseline/reference only |
| `txn_id` | Ingestion sequence identifier in this project | Not globally unique across independent producer runs unless configured |
| `variant` | Sticky A/B assignment based on sender ID | Recomputed by consumer |
| `produced_at`, `scored_at` | Producer/scoring timestamps | Used for end-to-end latency |
| `compute_ms` | Time spent scoring locally | Prefer for scorer performance |

Check the Kaggle dataset page for the exact version, row count, licence/terms, and file size before downloading; do not assume counts from comments in this repository.
