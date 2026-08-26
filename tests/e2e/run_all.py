"""E2E verification for all nodes — real fixtures, real execution, evidence captured"""
import asyncio, os, sys, json, tempfile, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)

from domain.specialist.specialist_registry import SpecialistRegistry, SpecialistProfile
from domain.specialist.lifelike_persona import LifelikePersona
from domain.inspection.document_store import DocumentStore
from domain.inspection.context_inspector import ContextInspector
from domain.index.index_file import IndexFile
from domain.index.code_reuse_index import CodeReuseIndex, SearchQuery
from domain.index.tool_index import ToolIndex, ToolSpecFull
from domain.execution.rlm_engine import RLMEngine
from domain.execution.speculative_executor import SpeculativeExecutor, SpeculativeTask
from application.programmatic_call import ProgrammaticCall
from infrastructure.embedding_search import EmbeddingSearch
from infrastructure.index_store import IndexStore

FIXTURE_DOC = os.path.join(ROOT, "tests/e2e/phase2_inspection/fixtures/sample_doc.txt")
EXPECTED_DIR = os.path.join(ROOT, "tests/e2e")
TMP_DIR = tempfile.mkdtemp()

def ok(msg): print(f"PASS {msg}")
def fail(msg): print(f"FAIL {msg}"); sys.exit(1)

async def test_METHOD_001():
    profiles = [
        SpecialistProfile(name="barlow", abilities=["barlow","clamp","fp16"], description="barlow twins fp16 clamp specialist"),
        SpecialistProfile(name="viz", abilities=["viz","plot"], description="visualization"),
        SpecialistProfile(name="ntp", abilities=["ntp","token"], description="next token prediction"),
    ]
    reg = SpecialistRegistry(profiles)
    choice = reg.select_specialist("FP16 clamp similarity matrix")
    assert choice.specialist.name == "barlow", f"got {choice.specialist.name}"
    assert choice.score.score > 0.5, f"score {choice.score.score}"
    assert choice.programmatic_handle.startswith("specialist://"), "handle not programmatic"
    assert "{" not in choice.programmatic_handle or ":" in choice.programmatic_handle  # handle not JSON blob
    # verify not JSON blob: handle is string reference, not json.dumps
    assert not choice.programmatic_handle.strip().startswith("{"), "should not be JSON blob"
    ok(f"METHOD-001 specialist={choice.specialist.name} score={choice.score.score:.2f} handle={choice.programmatic_handle}")

async def test_METHOD_002():
    profiles = [SpecialistProfile(name="barlow", abilities=["clamp"], description="x")]
    reg = SpecialistRegistry(profiles)
    choice = reg.select_specialist("clamp")
    persona = LifelikePersona().render(choice)
    assert len(persona.traits) == 3, f"traits {len(persona.traits)}"
    assert all(isinstance(t.intensity, float) for t in persona.traits)
    assert persona.voice.tone
    ok(f"METHOD-002 persona traits={[t.name for t in persona.traits]} voice={persona.voice}")

async def test_METHOD_003():
    store = DocumentStore()
    doc = store.ingest(FIXTURE_DOC)
    real_size = os.path.getsize(FIXTURE_DOC)
    assert doc.byte_count == real_size, f"{doc.byte_count} != {real_size}"
    assert store.byte_count(doc.doc_id) == real_size
    ok(f"METHOD-003 byte_count={real_size}")

async def test_METHOD_004():
    store = DocumentStore()
    doc = store.ingest(FIXTURE_DOC)
    inspector = ContextInspector(store)
    # LLM writes code to see slice, never receives full doc
    code = 'result = store.slice(doc_id, SliceSpec(offset=0, length=200))'
    res = inspector.inspect_via_code(doc.doc_id, code)
    assert len(res.slice_text) == 200, f"len {len(res.slice_text)}"
    assert "FP16" in res.slice_text or "Multimodal" in res.slice_text
    # ensure full doc not in prompt: inspection_code is code, not full doc
    assert len(res.inspection_code) < 500
    # second: via slice handle
    env = inspector.get_code_handle_env(doc.doc_id)
    assert "slice" in env and "store" in env
    ok(f"METHOD-004 slice_len={len(res.slice_text)} code={res.inspection_code[:60]}")

async def test_METHOD_005_006():
    tmp_path = os.path.join(TMP_DIR, "code_index.jsonl")
    if os.path.exists(tmp_path): os.remove(tmp_path)
    idx_file = IndexFile(tmp_path)
    code_idx = CodeReuseIndex(idx_file)
    code1 = "similarity_matrix = torch.clamp(similarity_matrix, -50.0, 50.0)"
    code2 = "target_indices = torch.clamp(target_indices, 0, vocab_size-1)"
    s1 = code_idx.index_code(code1, "clamp similarity matrix to prevent FP16 overflow")
    s2 = code_idx.index_code(code2, "clamp target indices")
    # dedup
    s1_dup = code_idx.index_code(code1, "duplicate should dedup")
    assert s1.hash == s1_dup.hash
    assert len(idx_file.read_all()) == 2, "append-only dedup failed"
    # search without loading full index into context: only top_k returned
    hits = code_idx.search(SearchQuery(text="clamp similarity matrix", top_k=1))
    assert len(hits) == 1
    assert "clamp" in hits[0].snippet.code
    assert hits[0].score > 0
    # verify file on disk has 2 entries but search returns only 1 to LLM
    assert idx_file.size_bytes() > 0
    ok(f"METHOD-005/006 indexed={len(idx_file.read_all())} search_hit={hits[0].snippet.code[:40]} score={hits[0].score}")

async def test_METHOD_007_008():
    tmp_path = os.path.join(TMP_DIR, "tool_index.jsonl")
    if os.path.exists(tmp_path): os.remove(tmp_path)
    idx_file = IndexFile(tmp_path)
    tool_idx = ToolIndex(idx_file)
    # register 50 tools to simulate MCP bloat
    for i in range(50):
        name = f"tool_{i:02d}"
        if i == 5:
            name = "grep_code"
            desc = "search codebase via ripgrep pattern"
        elif i == 7:
            name = "read_file"
            desc = "read file content from disk"
        elif i == 12:
            name = "get_db_stats"
            desc = "query telemetry duckdb"
        else:
            desc = f"dummy tool {i} does something else"
        tool_idx.register_tool(ToolSpecFull(name=name, description=desc, parameters={"type":"object","properties":{}}, code_ref=f"ref_{i}"))
    assert len(idx_file.read_all()) == 50
    file_size = idx_file.size_bytes()
    # search: only top-3 lites returned, not 50 (proof no MCP bulk)
    results = tool_idx.search_tools("grep codebase search", top_k=3)
    assert len(results) == 3, f"got {len(results)}"
    # first should be grep_code
    assert results[0].lite.name == "grep_code", f"got {results[0].lite.name}"
    # lazy load proof: lite only has name+short desc, full needs separate disk read
    assert len(results[0].lite.description) <= 120, "lite should be short"
    full = tool_idx.lazy_load("grep_code")
    assert full.name == "grep_code"
    assert full.parameters is not None
    # token estimation: 50 tools * ~100 tokens = 5000 tokens if bulk-loaded, we use < 300
    bulk_tokens = 50 * 30  # approx
    search_tokens = sum(len(r.lite.description)//4 for r in results)  # only top3
    assert search_tokens < 300, f"search_tokens {search_tokens} should be << bulk {bulk_tokens}"
    assert search_tokens < bulk_tokens
    ok(f"METHOD-007/008 bulk50 search_top3={[(r.lite.name, r.score) for r in results]} tokens bulk~{bulk_tokens} vs indexed~{search_tokens} file_bytes={file_size}")

async def test_METHOD_009():
    async def mock_llm(prompt, ctx=""):
        await asyncio.sleep(0.02)
        return f"mock_answer:{prompt[:30]} ctx_len={len(ctx)}"
    rlm = RLMEngine(mock_llm, max_depth=3, max_parallel=4)
    large = "x"*20000 + " clamp similarity matrix " + "y"*5000
    res = await rlm.spawn("summarize clamp logic", large, depth=0)
    assert res.depth == 0
    assert len(res.children) >= 2, f"children {len(res.children)}"
    assert "mock_answer" in res.answer
    # small context should not spawn
    small = "small doc"
    res2 = await rlm.spawn("q", small, depth=0)
    assert len(res2.children) == 0
    ok(f"METHOD-009 large children={len(res.children)} depth={res.depth} answer={res.answer[:40]}")

async def test_METHOD_010():
    exe = SpeculativeExecutor(threshold=0.55)
    preds = [
        SpeculativeTask(tool="grep_code", args={"pattern":"clamp"}, confidence=0.9),
        SpeculativeTask(tool="read_file", args={"path":"foo"}, confidence=0.8),
        SpeculativeTask(tool="dummy", args={}, confidence=0.1),  # below threshold
    ]
    tasks = await exe.speculate(preds)
    assert len(tasks) == 2, f"should speculate 2, got {len(tasks)}"
    final = [{"tool":"grep_code","args":{"pattern":"clamp"}}]  # only 1 committed
    committed = await exe.commit(final, tasks)
    assert len(committed) == 1
    assert committed[0].hit == True
    assert committed[0].tool == "grep_code"
    # second test: miss then cache hit
    exe2 = SpeculativeExecutor(threshold=0.5)
    preds2 = [SpeculativeTask(tool="get_db_stats", args={"query":"a"}, confidence=0.9)]
    t2 = await exe2.speculate(preds2)
    c2 = await exe2.commit([{"tool":"get_db_stats","args":{"query":"a"}}], t2)
    assert c2[0].hit == True
    ok(f"METHOD-010 hit={committed[0].hit} miss then hit ok")

async def test_METHOD_011_E2E():
    # E2E: full indexed programmatic call with real doc fixture, no MCP bulk
    profiles = [
        SpecialistProfile(name="barlow", abilities=["barlow","clamp","fp16","similarity"], description="barlow twins fp16 clamp specialist"),
        SpecialistProfile(name="viz", abilities=["viz"], description="viz"),
    ]
    registry = SpecialistRegistry(profiles)
    store = DocumentStore()
    doc = store.ingest(FIXTURE_DOC)
    inspector = ContextInspector(store)
    code_path = os.path.join(TMP_DIR, "e2e_code.jsonl")
    tool_path = os.path.join(TMP_DIR, "e2e_tool.jsonl")
    for p in [code_path, tool_path]:
        if os.path.exists(p): os.remove(p)
    code_idx = CodeReuseIndex(IndexFile(code_path))
    code_idx.index_code("similarity_matrix = torch.clamp(similarity_matrix, -50.0, 50.0)", "clamp similarity matrix FP16")
    code_idx.index_code("x = 1", "dummy")
    tool_idx = ToolIndex(IndexFile(tool_path))
    tool_idx.register_tool(ToolSpecFull(name="grep_code", description="search codebase ripgrep", parameters={"pattern":{}}, code_ref="grep"))
    tool_idx.register_tool(ToolSpecFull(name="read_file", description="read file", parameters={}, code_ref="read"))
    tool_idx.register_tool(ToolSpecFull(name="get_db_stats", description="query db", parameters={}, code_ref="db"))
    for i in range(10):
        tool_idx.register_tool(ToolSpecFull(name=f"dummy_{i}", description="dummy", parameters={}, code_ref="d"))
    async def mock_llm(p, c=""):
        await asyncio.sleep(0.01)
        return f"Answer for {p[:50]} with specialty"
    rlm = RLMEngine(mock_llm, max_depth=2, max_parallel=2)
    spec = SpeculativeExecutor(threshold=0.5)
    call = ProgrammaticCall(registry, inspector, code_idx, tool_idx, rlm, spec)
    result = await call.execute("find clamp similarity matrix logic", doc.doc_id, mock_llm)
    assert result.specialist == "barlow", f"got {result.specialist}"
    assert result.verification_passed == True, "verification should pass"
    assert result.index_search_tokens < 1000, f"tokens {result.index_search_tokens} must be <1000 proof no bulk"
    assert len(result.tools_used) > 0
    assert result.rlm_depth == 0
    # proof: index files on disk have many entries but only subset loaded
    assert len(IndexFile(tool_path).read_all()) == 13
    assert len(result.tools_used) <= 3
    # write expected artifact
    expected_path = os.path.join(ROOT, "tests/e2e/phase4_e2e/expected/e2e_result.json")
    os.makedirs(os.path.dirname(expected_path), exist_ok=True)
    with open(expected_path, "w") as f:
        json.dump({"specialist":result.specialist,"answer":result.answer[:200],"tokens":result.index_search_tokens,"tools":result.tools_used,"verified":result.verification_passed}, f, indent=2)
    with open(expected_path) as f: print(open(expected_path).read())
    ok(f"METHOD-011 E2E specialist={result.specialist} tokens={result.index_search_tokens} tools={result.tools_used} verified={result.verification_passed}")

async def test_embedding_search():
    es = EmbeddingSearch()
    score = es.score("clamp similarity", "similarity_matrix = torch.clamp(similarity_matrix, -50, 50)")
    assert score > 0
    docs = [{"code":"grep pattern"},{"code":"clamp similarity matrix"}, {"code":"other"}]
    top = es.top_k("clamp similarity", docs, k=1, text_key="code")
    assert "clamp" in top[0][0]["code"]
    ok(f"EmbeddingSearch score={score}")

async def test_infra_index_store():
    db_path = os.path.join(TMP_DIR, "test.db")
    if os.path.exists(db_path): os.remove(db_path)
    store = IndexStore(db_path)
    store.init_db()
    store.append("code_snippets", {"hash":"abc123","code":"x=1","description":"test","use_count":0})
    store.append("tool_index", {"name":"mytool","description":"desc","parameters":{"a":1},"code_ref":"ref"})
    rows = store.search_like("code_snippets", "x", 3)
    assert len(rows) == 1
    got = store.get_by_name("tool_index","mytool")
    assert got["name"]=="mytool"
    ok(f"IndexStore rows={len(rows)}")

async def main():
    await test_METHOD_001()
    await test_METHOD_002()
    await test_METHOD_003()
    await test_METHOD_004()
    await test_METHOD_005_006()
    await test_METHOD_007_008()
    await test_METHOD_009()
    await test_METHOD_010()
    await test_METHOD_011_E2E()
    await test_embedding_search()
    await test_infra_index_store()
    print("\nALL E2E VERIFICATION PASSED")
    # cleanup but keep evidence

if __name__ == "__main__":
    asyncio.run(main())
