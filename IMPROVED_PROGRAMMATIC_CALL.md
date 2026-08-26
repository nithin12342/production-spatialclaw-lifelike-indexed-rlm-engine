# Improved Programmatic Call — RLM + Indexed + Speculative (vs MCP)

## Problem (MCP anti-pattern)
- MCP loads 50-200 tool specs JSON into context each call: `50 * 500 tokens = 25k tokens` wasted
- Full code snippets + full docs stuffed into prompt → window overflow
- JSON-for-everything: `{"tool":"grep_code","args":{...}}` as primary interface

## Solution: Indexed Programmatic Call

### 1. Not JSON-for-everything — programmatic handles
```python
# domain/specialist/specialist_registry.py:28
choice = registry.select_specialist("FP16 clamp")  # returns SpecialistChoice object
# handle = "specialist://barlow#9abf" — object ref, not JSON blob
persona = LifelikePersona().render(choice)  # pure data, 3 traits, no I/O
```

### 2. LLM programs to see context (not prompt-stuffing)
```python
# domain/inspection/context_inspector.py:12
# LLM NEVER receives full doc. It writes code:
inspection = inspector.inspect_via_code(doc_id, 'result = store.slice(doc_id, SliceSpec(offset=0, length=800))')
# or via handle: slice(offset=1024, length=500) — only slice returned
# DocumentStore.ingest is immutable; slicing is view-only
```

### 3. Code reuse via indexed search (built incrementally)
```python
# domain/index/code_reuse_index.py:18, domain/index/index_file.py:14
code_idx = CodeReuseIndex(IndexFile("index_data/code_index.jsonl"))  # file on disk, append-only
code_idx.index_code("similarity_matrix = torch.clamp(...)", "clamp FP16") # deduplicated by md5
hits = code_idx.search(SearchQuery("clamp similarity", top_k=2))  # only 2 returned to LLM, not full file
# File: 2 entries on disk (313 bytes), LLM sees ~30 tokens, not bulk
```

### 4. Tool index stays on disk — lazy load top-k only (avoid MCP window filling)
```python
# domain/index/tool_index.py:13, infrastructure/index_store.py:12
tool_idx = ToolIndex(IndexFile("index_data/tool_index.jsonl")) # 22 tools on disk (2k bytes, SQLite alt)
results = tool_idx.search_tools("grep codebase", top_k=3)  # returns 3 lites (name+short desc), not 22
# MCP would load: 22 * 120 tokens = 2640 tokens
# Indexed: 3 * 8 tokens = 24 tokens (evidence: index_search_tokens=24 in e2e_result.json)
full = tool_idx.lazy_load("grep_code")  # full spec loaded ONLY when needed, via disk read
```

### 5. RLM + Speculative (unbounded context + latency)
```python
# domain/execution/rlm_engine.py:15, domain/execution/speculative_executor.py:14
rlm = RLMEngine(llm_call, max_depth=3, max_parallel=4)
spec = SpeculativeExecutor(threshold=0.55)

# Unified orchestrator application/programmatic_call.py:31
result = await ProgrammaticCall(registry, inspector, code_idx, tool_idx, rlm, spec).execute(
    query="find clamp similarity matrix logic",
    doc_id=doc.doc_id,
    llm_call=mock_llm
)
# Steps: specialist -> code-inspect -> indexed code search -> indexed tool search (top3) -> lazy load -> RLM spawn -> speculate -> commit -> verify
# Verified: result.verification_passed == True, result.index_search_tokens=24 (<1000 proves no bulk)
```

## Verification Evidence (tests/e2e/run_all.py)
```
PASS METHOD-001 specialist=barlow score=1.07 handle=specialist://barlow#9abf  # programmatic, not JSON
PASS METHOD-003 byte_count=777  # real fixture sample_doc.txt
PASS METHOD-004 slice_len=200 code=result = store.slice(...)  # code-as-inspection
PASS METHOD-005/006 indexed=2 search_hit=similarity_matrix... score=1.667  # indexed reuse
PASS METHOD-007/008 bulk50 search_top3=[('grep_code',1.0)] tokens bulk~1500 vs indexed~24 file_bytes=7326  # MCP vs indexed
PASS METHOD-009 large children=4 depth=0  # RLM parallel spawn
PASS METHOD-010 hit=True  # speculative commit
PASS METHOD-011 E2E specialist=barlow tokens=24 tools=['grep_code','read_file'] verified=True  # full flow idempotent
IDEMPOTENT_PASS
```

## Index Files on Disk (not in context)
- index_data/code_index.jsonl: 313 bytes, 2 entries — searchable, append-only, dedup
- index_data/tool_index.jsonl: 2029 bytes, 22 entries — only top_k=3 loaded per query
- Alternative: infrastructure/index_store.py uses SQLite (tool_index, code_snippets tables)

## File Responsibilities (SRP, <=7 words)
- FILE-001 specialist_registry.py: "rank and select specialist"
- FILE-003 context_inspector.py: "programmatic context inspection via code"
- FILE-005 code_reuse_index.py: "index and search code snippets"
- FILE-006 tool_index.py: "indexed tool search, lazy load"
- FILE-007 index_file.py: "persist index file on disk"
- FILE-010 programmatic_call.py: "orchestrate indexed programmatic call"

Traceability: REQ-004 -> SPEC-004 -> SOT-003 -> FOLDER-003 -> FILE-006 -> METHOD-007 -> VERIFY-007 (search_tools top-k lazy)
