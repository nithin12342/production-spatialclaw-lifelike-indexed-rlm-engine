import asyncio, os, sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from infrastructure.dataset_downloader import DatasetDownloader
from application.benchmark_verifier import BenchmarkVerifier

def ok(m): print(f"PASS {m}")
def fail(m): print(f"FAIL {m}"); sys.exit(1)

async def test_METHOD_019():
    dl = DatasetDownloader(data_root="data")
    # Download ERQA — should be idempotent (already downloaded 7 files)
    res = dl.download("ERQA")
    assert res["benchmark"] == "ERQA", res
    assert res["files"] > 0, f"files {res['files']}"
    # manifest exists
    assert os.path.exists("data/ERQA/manifest.json") or os.path.exists("verification/dataset/ERQA/manifest.json")
    # idempotent second run should be skipped
    res2 = dl.download("ERQA")
    assert res2["skipped"] == True or res2["files"] > 0
    samples = dl.get_samples("ERQA", limit=1)
    assert len(samples) == 1, f"samples {len(samples)}"
    assert "question" in samples[0] and "sample_id" in samples[0]
    ok(f"METHOD-019 download ERQA files={res['files']} skipped={res.get('skipped')} sample_id={samples[0]['sample_id']}")

async def test_METHOD_020():
    bv = BenchmarkVerifier(data_root="data", verification_root="verification/dataset")
    # Use first ERQA sample
    dl = DatasetDownloader(data_root="data")
    samples = dl.get_samples("ERQA", limit=1)
    sample = samples[0]
    res = await bv.verify_program("ERQA", sample, 0, work_dir_base="work_dir/benchmark_test")
    assert res["sample_id"] == sample["sample_id"]
    assert res["operational"] == "PASS", f"operational {res['operational']}"
    assert os.path.exists(res["sample_dir"] + "/input.json")
    assert os.path.exists(res["sample_dir"] + "/output.json")
    assert os.path.exists(res["sample_dir"] + "/step_000_input.json")
    assert os.path.exists(res["sample_dir"] + "/step_000_output.json")
    # Check per-step operationality
    step_out = json.loads(open(os.path.join(res["sample_dir"], "step_000_output.json")).read())
    assert "operational" in step_out
    ok(f"METHOD-020 verify_program sample={res['sample_id']} operational={res['operational']} steps={res['steps']} dir={res['sample_dir']}")

async def test_METHOD_021():
    bv = BenchmarkVerifier(data_root="data", verification_root="verification/dataset")
    summary = await bv.run_all_sequential(benchmark="ERQA", limit=3, work_dir_base="work_dir/benchmark_e2e")
    assert summary["benchmark"] == "ERQA"
    assert summary["samples_run"] == 3, f"run {summary['samples_run']}"
    assert summary["operational_pass"] == 3, f"pass {summary['operational_pass']}"
    assert os.path.exists("verification/dataset/ERQA/summary.json")
    assert os.path.exists("verification/dataset/ERQA/manifest.json")
    # Check detailed folders exist per SKELETON acceptance
    for s in summary["samples"]:
        sd = pathlib.Path(s["sample_dir"])
        assert (sd / "input.json").exists()
        assert (sd / "output.json").exists()
        assert len(list(sd.glob("step_*_input.json"))) >= 1
    # Also check tests/e2e expected
    assert os.path.exists("tests/e2e/phase7_dataset/expected/summary.json")
    ok(f"METHOD-021 run_all_sequential 3 samples PASS summary={summary['operational_pass']}/3")

async def main():
    await test_METHOD_019()
    await test_METHOD_020()
    await test_METHOD_021()
    print("\nALL DATASET E2E PASSED")

if __name__ == "__main__":
    asyncio.run(main())
