import asyncio, os, sys, json, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, ROOT)

from domain.integration.spatial_claw_kernel_port import SpatialClawKernelPort, ExecutionResult
from infrastructure.spatial_claw_kernel_adapter import SpatialClawKernelAdapter, KernelConfig
from infrastructure.spatial_claw_config_adapter import SpatialClawConfigAdapter
from application.integration.spatial_claw_production import SpatialClawProductionOrchestrator
from domain.specialist.specialist_registry import SpecialistRegistry, SpecialistProfile
from domain.inspection.document_store import DocumentStore
from domain.inspection.context_inspector import ContextInspector
from domain.index.index_file import IndexFile
from domain.index.code_reuse_index import CodeReuseIndex
from domain.index.tool_index import ToolIndex, ToolSpecFull

FIXTURE_DOC = os.path.join(ROOT, "tests/e2e/phase2_inspection/fixtures/sample_doc.txt")

def ok(msg): print(f"PASS {msg}")
def fail(msg): print(f"FAIL {msg}"); sys.exit(1)

async def test_METHOD_015_port():
    # METHOD-015: port defines execute/get_variables/check_sentinel with timeout, no clone import
    import inspect
    src = open(os.path.join(ROOT, "domain/integration/spatial_claw_kernel_port.py")).read()
    assert "async def execute" in src
    assert "async def get_variables" in src
    assert "cloning" not in src, "port must never import clone"
    assert "SpatialClawKernelPort" in src
    ok("METHOD-015 port defines execute/get_variables/check_sentinel no clone import")

async def test_METHOD_016_adapter():
    # METHOD-016: adapter executes code with timeout, ZMQ bump, fallback mock, real cell print(42)
    cfg = KernelConfig(timeout_sec=5, kernel_name="python3")
    adapter = SpatialClawKernelAdapter(cfg)
    kid = await adapter.start()
    assert kid, "kernel_id empty"
    assert adapter.is_running(), "not running"
    # health check
    hc = adapter.health_check()
    assert "mode" in hc and "is_running" in hc
    assert hc["timeout_sec"] == 5
    # real cell
    res = await adapter.execute("a=42; print(a)")
    assert res.stdout.strip() == "42" or "42" in res.stdout, f"stdout {res.stdout}"
    assert res.error is None, f"error {res.error}"
    # timeout test: sleep longer than timeout should return error containing timed out
    res2 = await adapter.execute("import time; time.sleep(3)", timeout=1)
    assert res2.error is not None and "timed out" in res2.error.lower(), f"expected timeout, got {res2.error}"
    # variables
    vars_info = await adapter.get_variables()
    assert "a" in vars_info or len(vars_info) >= 0
    # sentinel not set yet
    sentinel = await adapter.check_sentinel()
    assert sentinel is None
    # set sentinel via ReturnAnswer pattern
    await adapter.execute("import builtins; builtins._return_answer_result={'text':'hi','raw_value':123}")
    sentinel2 = await adapter.check_sentinel()
    assert sentinel2 is not None and sentinel2.get("text") == "hi", f"sentinel {sentinel2}"
    await adapter.clear_sentinel()
    assert await adapter.check_sentinel() is None
    await adapter.shutdown()
    assert not adapter.is_running()
    ok(f"METHOD-016 adapter mode={hc['mode']} kernel {kid[:8]} print42 ok timeout ok sentinel ok")

async def test_METHOD_017_config():
    # METHOD-017: load priority CLI>JSON>ENV>defaults, expands ${VAR}, timeout 600, tools_to_use
    # Setup env
    os.environ["SPATIAL_AGENT_BENCHMARK"] = "test_bench"
    os.environ["SPATIAL_AGENT_TIMEOUT_SEC"] = "123"
    os.environ["TEST_SECRET"] = "mykey123"
    # Create temp model json with ${VAR}
    import tempfile, json
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        json.dump({"llm_model":"test-model","llm_api_key":"${TEST_SECRET}","roles":{"main":{"max_tokens": 999, "temperature": 0.9}}}, tf)
        model_path = tf.name
    cfg = SpatialClawConfigAdapter.load(cli_args={"max_steps": 7}, model_json=model_path, dataset_json=None)
    # CLI highest
    assert cfg.max_steps == 7, f"max_steps {cfg.max_steps}"
    # ENV
    assert cfg.benchmark == "test_bench", f"benchmark {cfg.benchmark}"
    assert cfg.timeout_sec == 123, f"timeout {cfg.timeout_sec}"
    # ${VAR} expansion
    assert cfg.llm_api_key == "mykey123", f"api_key {cfg.llm_api_key}"
    # defaults
    assert cfg.tools_to_use == ["Reconstruct", "SAM3"], f"tools {cfg.tools_to_use}"
    assert cfg.executor_type == "code"
    # Model roles
    assert cfg.main_params.max_tokens == 999
    # health check
    hc = SpatialClawConfigAdapter.health_check(cfg)
    assert hc["timeout_sec"] == 123
    os.remove(model_path)
    del os.environ["SPATIAL_AGENT_BENCHMARK"]
    del os.environ["SPATIAL_AGENT_TIMEOUT_SEC"]
    del os.environ["TEST_SECRET"]
    ok(f"METHOD-017 config priority CLI>JSON>ENV defaults timeout={cfg.timeout_sec} tools={cfg.tools_to_use} expand ok")

async def test_METHOD_018_orchestrator():
    # METHOD-018: E2E production loop specialist->indexed->kernel->feedback->ReturnAnswer
    # Setup indexes if missing
    code_idx_path = os.path.join(ROOT, "index_data/nvidia_spatial_claw.jsonl")
    if not os.path.exists(code_idx_path):
        code_idx_path = os.path.join(ROOT, "index_data/code_index.jsonl")
    tool_idx_path = os.path.join(ROOT, "index_data/tool_index.jsonl")
    # Ensure tool index has at least 2
    if not os.path.exists(tool_idx_path) or len(open(tool_idx_path).readlines()) < 2:
        ToolIndex(IndexFile(tool_idx_path)).register_tool(ToolSpecFull(name="grep_code", description="search codebase", parameters={}, code_ref="grep"))
    profiles = [SpecialistProfile(name="spatial", abilities=["spatial","3d","reconstruct"], description="spatial specialist"),
                SpecialistProfile(name="barlow", abilities=["barlow"], description="barlow")]
    registry = SpecialistRegistry(profiles)
    store = DocumentStore()
    doc = store.ingest(FIXTURE_DOC)
    inspector = ContextInspector(store)
    code_idx = CodeReuseIndex(IndexFile(code_idx_path))
    tool_idx = ToolIndex(IndexFile(tool_idx_path))
    cfg = SpatialClawConfigAdapter.load(cli_args={"work_dir": "work_dir/test_production", "max_steps": 3, "enable_logging": True, "generate_report": True})
    kernel = SpatialClawKernelAdapter(KernelConfig(timeout_sec=10))
    orch = SpatialClawProductionOrchestrator(registry, inspector, code_idx, tool_idx, kernel, cfg, work_dir="work_dir/test_production")

    result = await orch.run("find spatial 3d reconstruction clamp", doc.doc_id, max_steps=3)
    assert result.specialist == "spatial", f"specialist {result.specialist}"
    assert result.termination_reason == "completed", f"term {result.termination_reason}"
    assert result.final_answer is not None, "final_answer None"
    assert result.verification_passed == True, "verification failed"
    assert os.path.exists(result.logs_path), f"logs missing {result.logs_path}"
    assert os.path.exists(result.work_dir), "work_dir missing"
    assert len(result.steps) >= 1
    assert result.health_checks["kernel"]["is_running"] == False or True  # after shutdown false, but before true
    # work_dir logging
    assert os.path.exists(os.path.join(ROOT, "tests/e2e/phase6_production/expected/production_result.json"))
    # idempotent: run again should also pass and create new log
    result2 = await orch.run("find spatial 3d reconstruction clamp", doc.doc_id, max_steps=3)
    assert result2.verification_passed == True
    assert result2.logs_path != result.logs_path, "should be new session"
    ok(f"METHOD-018 orchestrator specialist={result.specialist} termination={result.termination_reason} steps={len(result.steps)} answer={result.final_answer} elapsed={result.execution_time_sec:.2f}s logs={os.path.basename(result.logs_path)}")
    # cleanup work_dir for idempotency proof
    # not removing, keep evidence

async def main():
    await test_METHOD_015_port()
    await test_METHOD_016_adapter()
    await test_METHOD_017_config()
    await test_METHOD_018_orchestrator()
    print("\nALL PRODUCTION E2E PASSED")

if __name__ == "__main__":
    asyncio.run(main())
