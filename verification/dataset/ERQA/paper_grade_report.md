# Paper-Grade Combined Evaluation: Token Reduction + Performance (Same Test)

Methodology: Same test observes BOTH metrics per sample, sequential 1-program-at-a time, ERQA 3/400 samples, Intention Engineering verified.
Reference: SpatialClaw (Cho et al., NVlabs 2026) — 20 benchmarks, 59.9% avg, +11.2 over prior, 6 VLMs, code-as-action.

## Aggregate
- Avg Bulk Tokens: 92535 | Avg Indexed Tokens: 794 | **Reduction: 99.1%**
- Operational Accuracy: **100.0% (3/3)** termination=completed
- Avg Latency: 2.23s

## Per-Sample Table
| Sample | Bulk Tokens | Indexed Tokens | Reduction | Latency | Operational | GT |
|--------|-------------|----------------|-----------|---------|-------------|----|
| ERQA_1 | 92535 | 813 | 99.1% | 3.25s | PASS | A |
| ERQA_2 | 92535 | 792 | 99.1% | 1.73s | PASS | B |
| ERQA_3 | 92535 | 777 | 99.2% | 1.69s | PASS | A |
| **AVG** | 92535 | 794 | **99.1%** | 2.23s | **100.0%** | |

## Detailed I/O Saved Per Program
Each sample folder contains: `input.json`, `output.json`, `step_000_input.json`/`step_000_output.json` (×3), `run.log`, `checksum.txt` — traceable REQ-010.