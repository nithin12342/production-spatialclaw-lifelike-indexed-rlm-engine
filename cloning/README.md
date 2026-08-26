# cloning/ — Isolated External Repository Clones

> Intention Engineering Extension: This folder is **outside** `domain/`/`application/`/`infrastructure/` to preserve DIP. Cloned repos are never imported directly by domain. Useful code is extracted via `infrastructure/clone_indexer.py` -> `domain/index/code_reuse_index.py` (indexed search), so no context window filling.

## SOT for This Extension (observed before coding)
- **REQ-008**: Clone special-flower repository in separate `cloning/` folder and extract useful code via indexed search — SPEC-008 — SOT-005 (new bounded context: AcquisitionContext)
- Aggregates: `ExternalClone` (invariant: clone is immutable after fetch, only indexed views returned), `CloneIndexer`
- Nodes: METHOD-012 `clone_repo`, METHOD-013 `index_external_code`, METHOD-014 `search_external`
- Data flow: `AcquisitionContext -> IndexContext -> ExecutionContext`
- File: `infrastructure/clone_indexer.py:1` — responsibility: "clone and index external repo" — must never decide specialty
- Verification: `tests/e2e/phase5_clone/fixtures` + `expected/clone_index.json` — clone exists, file count >0, search returns hit without loading full repo into LLM

## Usage
```bash
# Clone any external repo (e.g., special-flower) isolated here:
git clone <SPECIAL_FLOWER_URL> cloning/special-flower

# Index useful code (programmatic, not prompt stuffing):
python -m infrastructure.clone_indexer --source cloning/special-flower --index index_data/external_code.jsonl --pattern "*.py"

# Search without loading full repo into LLM window:
python -c "from domain.index.code_reuse_index import CodeReuseIndex; from domain.index.index_file import IndexFile; idx=CodeReuseIndex(IndexFile('index_data/external_code.jsonl')); print(idx.search(...))"
```

## Isolation Rules (principles.md:3 SOLID)
- domain/ NEVER imports from cloning/ — enforced
- Only infrastructure/ reads cloning/ files and writes to index_data/
- application/ orchestrates via CodeReuseIndex search (top-k), not bulk load
