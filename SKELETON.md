# SKELETON.md — Lifelike Indexed Programmatic Engine

> Intention Engineering skeleton. Source of truth. Code must not drift from this.

## System
LifelikeIndexedProgrammaticEngine — Replaces MCP-style JSON-everything tool filling with programmatic, indexed, lifelike specialist execution. LLM writes code to inspect context/documents, reuses indexed code snippets, and lazily loads only necessary tool specs from disk index (never bulk-loading index into context window). Combines RLM recursion + speculative execution.

## Requirements
- REQ-001: Route to best lifelike specialist ability via programmatic call (not JSON for everything) — SPEC-001
- REQ-002: Context management where LLM programs to see what is in context/documents (code-as-inspection, not prompt-stuffing) — SPEC-002
- REQ-003: Reuse code LLM writes again and again via incremental index built under program, searchable to find right snippet — SPEC-003
- REQ-004: Avoid MCP-like context window filling — tool call details are NOT bulk-loaded; index stays on disk, only necessary tools lazily loaded — SPEC-004
- REQ-005: Index file (infrastructure file) used to search/find necessary tools/code to run — SPEC-005
- REQ-006: Combine with RLM recursion + speculative execution for latency and unbounded context — SPEC-006
- REQ-007: Verification-first: every node compiles clean + E2E fixture produces expected artifact — SPEC-007
- REQ-008: Clone nvidia spatial claw (NVlabs/SpatialClaw) repository in separate cloning/ folder and extract useful code via indexed search (extend skill beyond coding: observe SOT first) — SPEC-008
- REQ-009: Integrate NVlabs/SpatialClaw production-ready kernel+config+loop completely with LifelikeIndexedProgrammaticEngine, production-ready error handling, timeouts, observability — SPEC-009

## Bounded Contexts

### 1. SpecialistContext
- reason_separate: owns lifelike persona/specialist selection, nothing else decides who is best
- sot_id: SOT-001
- aggregates:
  - name: SpecialistRegistry
    invariant: "Exactly one specialist is active per programmatic call; specialty never leaks into tool index"
    entities: [Specialist]
    value_objects: [SpecialistProfile, AbilityScore]
    ports_in: []
    ports_out: ["SpecialistChoice -> InspectionContext", "SpecialistChoice -> ExecutionContext"]
  - name: LifelikePersona
    invariant: "Persona traits are pure data, no I/O; rendering is separate from selection"
    entities: [Persona]
    value_objects: [Trait, Voice]
    ports_in: ["SpecialistChoice <- SpecialistRegistry"]
    ports_out: ["Persona -> ExecutionContext"]

### 2. InspectionContext
- reason_separate: owns programmatic context/document inspection, never touches specialist ranking
- sot_id: SOT-002
- aggregates:
  - name: ContextInspector
    invariant: "LLM never receives raw large context directly; it receives code handle to inspect it programmatically"
    entities: [InspectionSession]
    value_objects: [CodeHandle, InspectionQuery, DocumentSlice]
    ports_in: ["SpecialistChoice <- SpecialistContext", "DocumentInput (external)"]
    ports_out: ["InspectionResult -> IndexContext", "InspectionResult -> ExecutionContext"]
  - name: DocumentStore
    invariant: "Documents are immutable after ingestion; only slices/views are returned via code"
    entities: [Document]
    value_objects: [DocId, SliceSpec]
    ports_in: ["DocumentInput"]
    ports_out: ["Slice -> ContextInspector"]

### 3. IndexContext
- reason_separate: owns all indexed search (code reuse + tool index), stays on disk, never bulk-loads into LLM window
- sot_id: SOT-003
- aggregates:
  - name: CodeReuseIndex
    invariant: "Index is append-only; duplicate code hashes are deduplicated; search never loads full index into LLM context"
    entities: [CodeSnippet]
    value_objects: [Embedding, CodeHash, SearchQuery]
    ports_in: ["InspectionResult <- InspectionContext", "CodeWrite (from LLM)"]
    ports_out: ["SnippetHit -> ExecutionContext"]
  - name: ToolIndex
    invariant: "Tool index file stays on disk (sqlite/jsonl); only top-k tool specs are lazily loaded per search"
    entities: [ToolEntry]
    value_objects: [ToolSpecLite, IndexFileRef, SearchResult]
    ports_in: ["SearchQuery <- ExecutionContext"]
    ports_out: ["ToolSpecBatch -> ExecutionContext"]

### 4. ExecutionContext
- reason_separate: owns RLM recursion + speculative execution + verification gate, consumes others
- sot_id: SOT-004
- aggregates:
  - name: RLMEngine
    invariant: "Depth never exceeds max_depth; each spawn is isolated, synthesis merges children"
    entities: [RLMSession]
    value_objects: [SpawnRequest, SynthesisResult]
    ports_in: ["InspectionResult <- InspectionContext", "SnippetHit <- IndexContext", "ToolSpecBatch <- IndexContext"]
    ports_out: ["ExecutionResult -> outside"]
  - name: SpeculativeExecutor
    invariant: "Only speculative_safe tools are pre-executed; uncommitted tasks are cancelled"
    entities: [SpeculativeTask]
    value_objects: [Confidence, CacheKey]
    ports_in: ["ToolSpecBatch <- IndexContext"]
    ports_out: ["CommittedResult -> RLMEngine"]

### 5. AcquisitionContext (extension beyond coding)
- reason_separate: owns external repo cloning, isolated from domain, only indexed views leave
- sot_id: SOT-005
- aggregates:
  - name: ExternalClone
    invariant: "Clone is immutable after fetch; only indexed snippets leave cloning/ folder, never raw bulk"
    entities: [Clone]
    value_objects: [RepoUrl, ClonePath]
    ports_in: ["RepoUrl (external)"]
    ports_out: ["ClonePath -> IndexContext"]
  - name: CloneIndexer
    invariant: "Indexing is append-only dedup; search never loads full cloned repo into LLM context"
    entities: [CloneIndex]
    value_objects: [IndexFileRef, SearchQuery]
    ports_in: ["ClonePath <- ExternalClone"]
    ports_out: ["SnippetHit -> IndexContext"]

### 6. IntegrationContext (production-ready)
- reason_separate: owns production-ready SpatialClaw integration, bridges cloned kernel/config/loop into application, nothing else touches production wiring
- sot_id: SOT-006
- aggregates:
  - name: SpatialClawKernelAdapter
    invariant: "Kernel lifecycle is production-ready: timeout enforcement, ZMQ bump, restart-with-reinject, interrupt on timeout; never leaks clone import to domain"
    entities: [KernelSession]
    value_objects: [ExecutionResult, KernelConfig]
    ports_in: ["ClonePath <- AcquisitionContext", "Config <- IntegrationContext"]
    ports_out: ["ExecutionResult -> ExecutionContext"]
  - name: SpatialClawConfigAdapter
    invariant: "Config priority CLI > JSON > ENV (SPATIAL_AGENT_*) > defaults; env expansion ${VAR} supported"
    entities: [AgentConfig]
    value_objects: [LLMRoleParams, WorkDir]
    ports_in: ["EnvVars, JsonConfigs (external)"]
    ports_out: ["Config -> SpatialClawKernelAdapter"]
  - name: SpatialClawOrchestrator
    invariant: "Orchestrates 5-stage SpatialClaw loop (Planning->CodeGen->Execute->Feedback->ReturnAnswer) via our Specialist+Index+RLM+Speculative, production logging, health checks"
    entities: [ProductionSession]
    value_objects: [AgentState, ChecklistItem, StepResult]
    ports_in: ["SpecialistChoice <- SpecialistContext", "SnippetHit <- IndexContext", "ToolSpecBatch <- IndexContext", "ExecutionResult <- SpatialClawKernelAdapter"]
    ports_out: ["ProductionResult -> outside"]

## Data Flow Order
[SpecialistContext, InspectionContext, IndexContext, ExecutionContext, AcquisitionContext, IntegrationContext]

## Folders (Phase 1 output)
- FOLDER-001: domain/specialist — SpecialistRegistry, LifelikePersona — DIP: domain — Owner: SOT-001
- FOLDER-002: domain/inspection — ContextInspector, DocumentStore — DIP: domain — Owner: SOT-002
- FOLDER-003: domain/index — CodeReuseIndex, ToolIndex — DIP: domain — Owner: SOT-003
- FOLDER-004: domain/execution — RLMEngine, SpeculativeExecutor — DIP: domain — Owner: SOT-004
- FOLDER-005: application — orchestration, ports interfaces — DIP: application
- FOLDER-006: infrastructure — sqlite/file index impl, embeddings — DIP: infrastructure
- FOLDER-007: interfaces — CLI / programmatic API — DIP: interfaces
- FOLDER-008: tests/e2e — fixtures + expected per phase — DIP: tests
- FOLDER-009: cloning — isolated external clones, never imported by domain — DIP: external (outside DIP, isolated) — Owner: SOT-005
- FOLDER-010: domain/integration — SpatialClawKernelAdapter, SpatialClawConfigAdapter ports — DIP: domain — Owner: SOT-006
- FOLDER-011: application/integration — SpatialClawOrchestrator production — DIP: application — Owner: SOT-006

## Files (Phase 2 output)
- FILE-001: domain/specialist/specialist_registry.py — responsibility: "rank and select specialist" — sot: SOT-001 — must never: touch index I/O
- FILE-002: domain/specialist/lifelike_persona.py — responsibility: "render lifelike persona traits" — sot: SOT-001 — must never: decide routing
- FILE-003: domain/inspection/context_inspector.py — responsibility: "programmatic context inspection via code" — sot: SOT-002 — must never: load full docs into LLM prompt
- FILE-004: domain/inspection/document_store.py — responsibility: "store and slice documents" — sot: SOT-002 — must never: call LLM
- FILE-005: domain/index/code_reuse_index.py — responsibility: "index and search code snippets" — sot: SOT-003 — must never: bulk-load into context
- FILE-006: domain/index/tool_index.py — responsibility: "indexed tool search, lazy load" — sot: SOT-003 — must never: expose full index to LLM
- FILE-007: domain/index/index_file.py — responsibility: "persist index file on disk" — sot: SOT-003 — must never: do semantic ranking
- FILE-008: domain/execution/rlm_engine.py — responsibility: "recursive spawn and synthesize" — sot: SOT-004 — must never: own tool specs
- FILE-009: domain/execution/speculative_executor.py — responsibility: "speculative pre-execute and commit" — sot: SOT-004 — must never: speculate unsafe writes
- FILE-010: application/programmatic_call.py — responsibility: "orchestrate indexed programmatic call" — sot: SOT-004 — must never: implement domain invariants
- FILE-011: infrastructure/index_store.py — responsibility: "sqlite index file persistence" — sot: SOT-003 — must never: decide search ranking
- FILE-012: infrastructure/embedding_search.py — responsibility: "vector search over index" — sot: SOT-003 — must never: mutate index
- FILE-013: interfaces/cli.py — responsibility: "expose programmatic call CLI" — sot: SOT-004 — must never: contain business logic
- FILE-014: infrastructure/clone_indexer.py — responsibility: "clone and index external repo" — sot: SOT-005 — must never: decide specialty
- FILE-015: cloning/README.md — responsibility: "document isolated clone isolation" — sot: SOT-005 — must never: contain executable logic
- FILE-016: domain/integration/spatial_claw_kernel_port.py — responsibility: "define kernel port interface" — sot: SOT-006 — must never: import clone
- FILE-017: infrastructure/spatial_claw_kernel_adapter.py — responsibility: "adapt SpatialClaw kernel production" — sot: SOT-006 — must never: decide specialty
- FILE-018: infrastructure/spatial_claw_config_adapter.py — responsibility: "adapt SpatialClaw config production" — sot: SOT-006 — must never: execute code
- FILE-019: application/integration/spatial_claw_production.py — responsibility: "orchestrate production SpatialClaw loop" — sot: SOT-006 — must never: import clone directly
- FILE-020: interfaces/production_cli.py — responsibility: "expose production CLI" — sot: SOT-006 — must never: contain business logic

## Nodes (METHOD-level)
- METHOD-001: SpecialistRegistry.select_specialist — parent: FILE-001 — deps: [] — priority: critical — acceptance: "given 3 specialist profiles and query 'FP16 clamp', selects barlow specialist with score>0.7 and returns not JSON blob but SpecialistChoice object"
- METHOD-002: LifelikePersona.render — parent: FILE-002 — deps: [METHOD-001] — priority: normal — acceptance: "given SpecialistChoice, returns persona with 3 traits, no I/O"
- METHOD-003: DocumentStore.ingest — parent: FILE-004 — deps: [] — priority: high — acceptance: "ingest real file tests/e2e/phase2_inspection/fixtures/sample_doc.txt, byte count matches"
- METHOD-004: ContextInspector.inspect_via_code — parent: FILE-003 — deps: [METHOD-003] — priority: critical — acceptance: "LLM writes code `store.slice(0,100)` to inspect doc, never receives full doc in prompt, returns InspectionResult with slice"
- METHOD-005: CodeReuseIndex.index_code — parent: FILE-005 — deps: [] — priority: high — acceptance: "index 2 code snippets, deduplicates same hash, append-only"
- METHOD-006: CodeReuseIndex.search — parent: FILE-005 — deps: [METHOD-005] — priority: critical — acceptance: "search 'clamp similarity matrix' returns snippet with clamp code, without loading full index into context"
- METHOD-007: ToolIndex.search_tools — parent: FILE-006 — deps: [FILE-007] — priority: critical — acceptance: "given index file with 50 tools, search 'grep' returns top-3 specs only, not 50; index file size on disk >0, context tokens < 1k"
- METHOD-008: ToolIndex.lazy_load — parent: FILE-006 — deps: [METHOD-007] — priority: high — acceptance: "lazy_load tool 'grep_code' loads full spec from disk on demand, verified by file read"
- METHOD-009: RLMEngine.spawn — parent: FILE-008 — deps: [METHOD-004] — priority: critical — acceptance: "large doc 20k chars triggers chunk+parallel spawn depth1 with 2 children, synthesis returns"
- METHOD-010: SpeculativeExecutor.speculate_commit — parent: FILE-009 — deps: [METHOD-007] — priority: high — acceptance: "speculate 2 tools, commit 1 hit, unused cancelled"
- METHOD-011: ProgrammaticCall.execute — parent: FILE-010 — deps: [METHOD-001, METHOD-004, METHOD-006, METHOD-007, METHOD-009, METHOD-010] — priority: critical — acceptance: "E2E: query 'find clamp' with real doc fixture, uses indexed search not MCP bulk, returns verified answer with hits>0, full flow"
- METHOD-012: CloneIndexer.clone_repo — parent: FILE-014 — deps: [] — priority: high — acceptance: "clone url to cloning/special-flower, folder exists with >0 files, idempotent second run adds 0"
- METHOD-013: CloneIndexer.index_external_code — parent: FILE-014 — deps: [METHOD-012] — priority: high — acceptance: "walk cloning/special-flower *.py max 200, append dedup to index_data/external_code.jsonl, count>0, second run 0"
- METHOD-014: CloneIndexer.search_external — parent: FILE-014 — deps: [METHOD-013] — priority: critical — acceptance: "search 'clamp' in external index returns hit without loading full repo into LLM context, tokens <500"
- METHOD-015: SpatialClawKernelPort.execute — parent: FILE-016 — deps: [] — priority: high — acceptance: "port defines execute/get_variables/check_sentinel with timeout, no clone import"
- METHOD-016: SpatialClawKernelAdapter.execute — parent: FILE-017 — deps: [FILE-016, METHOD-012] — priority: critical — acceptance: "adapter executes code with timeout, ZMQ bump, interrupt on timeout, fallback mock if jupyter missing, verified with real cell print(42)"
- METHOD-017: SpatialClawConfigAdapter.load — parent: FILE-018 — deps: [] — priority: high — acceptance: "load priority CLI>JSON>ENV(SPATIAL_AGENT_*)>defaults, expands ${VAR}, timeout_sec 600, tools_to_use [Reconstruct,SAM3]"
- METHOD-018: SpatialClawOrchestrator.run — parent: FILE-019 — deps: [METHOD-001, METHOD-004, METHOD-006, METHOD-007, METHOD-015, METHOD-016, METHOD-017] — priority: critical — acceptance: "E2E production loop: specialist->indexed tool search->kernel execute->feedback->ReturnAnswer, verified with real fixture, logging to work_dir, health check pass, idempotent"

## Traceability Chain Example
REQ-004 -> SPEC-004 -> SOT-003 -> FOLDER-003 -> FILE-006 -> CLASS-ToolIndex -> METHOD-007 -> VERIFY-007
REQ-008 -> SPEC-008 -> SOT-005 -> FOLDER-009 -> FILE-014 -> CLASS-CloneIndexer -> METHOD-012 -> VERIFY-012
REQ-009 -> SPEC-009 -> SOT-006 -> FOLDER-010 -> FILE-017 -> CLASS-SpatialClawKernelAdapter -> METHOD-016 -> VERIFY-016

## Pattern Library Candidates (populated after verification)
- (pending) PATTERN-001: IndexedToolSearch (lazy load vs MCP bulk)
- (pending) PATTERN-002: CodeReuseDedupIndex
- (pending) PATTERN-003: ProgrammaticContextInspection (code-as-handle)
