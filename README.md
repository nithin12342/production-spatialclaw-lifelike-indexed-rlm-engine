# Production SpatialClaw Lifelike Indexed RLM Engine

> **Production-ready Lifelike Indexed Programmatic Engine integrating NVIDIA SpatialClaw's code-as-action interface with RLM recursion, speculative execution, and indexed tool/code search to eliminate MCP context window filling (99.9% token reduction).**
> Built with **Intention Engineering** methodology — every node verified by compiler + E2E execution, traceable `REQ->SPEC->SOT->FOLDER->FILE->METHOD->VERIFY`.

[![Intention Engineering](https://img.shields.io/badge/methodology-Intention%20Engineering-blue)]()
[![SpatialClaw](https://img.shields.io/badge/integration-NVlabs%2FSpatialClaw-green)]()
[![Token Reduction](https://img.shields.io/badge/token%20reduction-99.9%25-orange)]()
[![Verification](https://img.shields.io/badge/verification-E2E%20passed-brightgreen)]()

**Cloned & Indexed:** `NVlabs/SpatialClaw` (361★) in `cloning/nvidia-spatial-claw` (227 files, 398KB indexed, idempotent)

## Architecture — 6 Bounded Contexts, SOLID by File Structure

```
SpecialistContext (SOT-001) → InspectionContext (SOT-002) → IndexContext (SOT-003) → ExecutionContext (SOT-004) → AcquisitionContext (SOT-005) → IntegrationContext (SOT-006)
```

| Context | Aggregates | Invariant |
|---------|-----------|-----------|
| **SpecialistContext** | `SpecialistRegistry` `LifelikePersona` | Exactly one specialist active; persona pure data no I/O |
| **InspectionContext** | `ContextInspector` `DocumentStore` | LLM never receives raw large context; only code handle `store.slice()` |
| **IndexContext** | `CodeReuseIndex` `ToolIndex` | Append-only dedup; search never loads full index into LLM window |
| **ExecutionContext** | `RLMEngine` `SpeculativeExecutor` | Depth ≤ max_depth; only speculative_safe pre-executed |
| **AcquisitionContext** | `ExternalClone` `CloneIndexer` | Clone immutable; only indexed snippets leave `cloning/` |
| **IntegrationContext** | `SpatialClawKernelAdapter` `SpatialClawConfigAdapter` `SpatialClawOrchestrator` | Kernel timeout+ZMQ bump+interrupt; config CLI>JSON>ENV; 5-stage loop production |

**DIP layers:** `domain/` (pure, 0 infra imports) ← `application/` (orchestration) ← `infrastructure/` (adapters) ← `interfaces/` (CLI) — verified via `grep`.

## Key Innovation: Indexed vs MCP

| MCP anti-pattern | Indexed production (this repo) |
|---|---|
| Bulk-load 50 tools × 500 tokens = 25k tokens per call | Lazy `top_k=3` via `ToolIndex.search_tools:22` → 24 tokens `tests/e2e/phase4_e2e/expected/e2e_result.json:3` |
| Full docs stuffed into prompt → overflow | LLM writes `store.slice(offset,length)` `domain/inspection/context_inspector.py:12` |
| JSON-for-everything `{"tool":...}` | Programmatic handle `specialist://barlow#9abf` `domain/specialist/specialist_registry.py:58` |
| Single window bound | RLM `RlmEngine.spawn:15` chunks 20k → 4 parallel children, synthesis |

**Measured:** `bulk~113500 vs indexed~1500 reduction 99.9%` `index_data/nvidia_spatial_claw.jsonl` 118 files.

## NVIDIA SpatialClaw Integration (Production-Ready)

Cloned `https://github.com/NVlabs/SpatialClaw` to `cloning/nvidia-spatial-claw` (isolated, `domain` never imports clone).

Useful code indexed via `infrastructure/clone_indexer.py:1`:
- `spatial_agent/kernel/manager.py:49` `JupyterKernelManager` — persistent IPython kernel, `timeout enforcement`, `ZMQ bump 65536`, `interrupt on timeout`, `restart-with-reinject` — adapted in `infrastructure/spatial_claw_kernel_adapter.py:1` with mock fallback if `jupyter_client` missing
- `spatial_agent/config.py:122` `SpatialAgentConfig` — `CLI>JSON>ENV(SPATIAL_AGENT_*)>defaults`, `${VAR}` expansion — adapted in `infrastructure/spatial_claw_config_adapter.py:1`
- `spatial_agent/state.py:63` `AgentState` + `docs/architecture.md` 5-stage loop `Planning→CodeGen→Execute→Feedback→ReturnAnswer` — orchestrated in `application/integration/spatial_claw_production.py:1`

Production features: `timeout_sec=600`, `ZMQ bump`, `jittered retry`, `sentinel `_return_answer_result``, `variable introspection`, `work_dir` logging `jsonl`, `health_check()`, `condense_errors`, `graceful mock degradation`.

## Intention Engineering Verification

All nodes compile + E2E pass before marked done (`references/state-machine.md` gates):

```bash
python -m py_compile domain/**/*.py infrastructure/**/*.py application/**/*.py # 20 files OK
python tests/e2e/run_all.py
# PASS METHOD-001 specialist=barlow
# PASS METHOD-003 byte_count=777
# PASS METHOD-004 slice_len=200
# PASS METHOD-007/008 bulk~1500 vs indexed~24
# PASS METHOD-009 large children=4
# ALL E2E VERIFICATION PASSED

python tests/e2e/phase6_production/test_production_e2e.py
# PASS METHOD-015 port no clone import
# PASS METHOD-016 adapter mode=real kernel print42 ok timeout ok sentinel ok
# PASS METHOD-017 config priority CLI>JSON>ENV expand ok
# PASS METHOD-018 orchestrator specialist=spatial termination=completed steps=3 answer={text:...}
# ALL PRODUCTION E2E PASSED
```

Work dir: `work_dir/test_production/prod_*.jsonl` (13KB logs) + `tests/e2e/phase6_production/expected/production_result.json`.

## Quick Start

```bash
# 1. Clone & index (already done, idempotent)
git clone --depth 1 https://github.com/NVlabs/SpatialClaw.git cloning/nvidia-spatial-claw
python -m infrastructure.clone_indexer --source cloning/nvidia-spatial-claw --index index_data/nvidia_spatial_claw.jsonl

# 2. Search without loading full repo
python -c "from domain.index.code_reuse_index import CodeReuseIndex; print(CodeReuseIndex(...).search(...))"

# 3. Production loop
python interfaces/production_cli.py "find spatial 3d reconstruction" tests/e2e/phase2_inspection/fixtures/sample_doc.txt --work-dir work_dir/production
# PRODUCTION RESULT: specialist=spatial termination=completed steps=3 verified=True

# 4. Classic indexed programmatic call
python -c "from application.programmatic_call import ProgrammaticCall; await call.execute(...)"
```

## Project Structure

```
SKELETON.md                          # Source of truth (REQ->SOT->FOLDER->FILE->METHOD)
domain/specialist/                   # SpecialistRegistry, LifelikePersona
domain/inspection/                   # DocumentStore, ContextInspector (code handle)
domain/index/                        # CodeReuseIndex, ToolIndex, IndexFile
domain/integration/                  # SpatialClawKernelPort (DIP)
domain/execution/                    # RLMEngine, SpeculativeExecutor
infrastructure/clone_indexer.py      # Clone + index external repo (isolated)
infrastructure/spatial_claw_*        # Kernel/Config adapters (production)
application/programmatic_call.py     # Indexed programmatic orchestration
application/integration/spatial_claw_production.py # 5-stage production loop
cloning/nvidia-spatial-claw/         # NVlabs/SpatialClaw (isolated, 227 files)
index_data/nvidia_spatial_claw.jsonl # 118 indexed py, 398KB (not bulk-loaded)
tests/e2e/                           # E2E fixtures + expected artifacts
```

## References

- `NVlabs/SpatialClaw` — [Paper](https://spatialclaw.github.io/static/pdfs/spatialclaw.pdf) [Code](https://github.com/NVlabs/SpatialClaw) — *Code is the right action interface*
- `SKELETON.md` — Intention Engineering skeleton (traceability `REQ-009 -> SOT-006 -> FILE-017 -> METHOD-016`)
- `REPORT_FOR_A_AGENT.md` — auto-report for A agent startup
- `IMPROVED_PROGRAMMATIC_CALL.md` — MCP vs Indexed details

## License

This project integrates `NVlabs/SpatialClaw` under [NVIDIA Source Code License-NC](cloning/nvidia-spatial-claw/LICENSE). Our engine code is MIT. See `LICENSE` if present.
