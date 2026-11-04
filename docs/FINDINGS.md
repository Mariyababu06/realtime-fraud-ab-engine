# Findings template — populate only from real PaySim runs

> Do not report demo metrics as evidence. The bundled synthetic sample is for pipeline validation only.

## Dataset and cohort
- Dataset source/version:
- Download date and checksum:
- Rows processed / time range:
- Fraud prevalence:
- Exclusions and data-quality checks:

## Experiment design
- Randomisation unit: origin account (sticky assignment)
- Variants and rule versions:
- Primary metric: user-level fraud recall (define denominator precisely)
- Guardrails: false-positive rate, precision, fraud amount caught, p95/p99 scoring latency
- Minimum detectable effect / sample-size plan:
- SRM result:

## Results
| Metric | A | B | Difference (B − A) | 95% CI | Method |
|---|---:|---:|---:|---:|---|
| User-level fraud recall | | | | | User-cluster bootstrap |
| False-positive rate | | | | | User-cluster bootstrap |
| Precision | | | | | User-cluster bootstrap |
| p95 compute latency (ms) | | | | | Quantile |

## Decision and limitations
State the practical impact, uncertainty, cohort limits, data leakage risks, and whether the result replicates on a later holdout period. Statistical significance alone is not a launch criterion.
