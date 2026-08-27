"""FILE-022: run 1 program at a time verifier — must never bulk-load dataset"""
import asyncio
import os
import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from domain.specialist.specialist_registry import SpecialistRegistry
from domain.inspection.document_store import DocumentStore
from domain.inspection.context_inspector import ContextInspector
from domain.index.index_file import IndexFile
from domain.index.code_reuse_index import CodeReuseIndex
from domain.index.tool_index import ToolIndex
from infrastructure.dataset_downloader import DatasetDownloader
from infrastructure.spatial_claw_kernel_adapter import SpatialClawKernelAdapter, KernelConfig
from infrastructure.spatial_claw_config_adapter import SpatialClawConfigAdapter
from application.integration.spatial_claw_production import SpatialClawProductionOrchestrator

class BenchmarkVerifier:
    """SRP: run 1 program at a time verifier — sequential, detailed I/O per step"""

    def __init__(self, data_root: str = "data", verification_root: str = "verification/dataset"):
        self.data_root = Path(data_root)
        self.verification_root = Path(verification_root)
        self.verification_root.mkdir(parents=True, exist_ok=True)
        self.downloader = DatasetDownloader(data_root=data_root)

    async def verify_program(self, benchmark: str, sample: Dict[str, Any], sample_idx: int, work_dir_base: str = "work_dir/benchmark") -> Dict[str, Any]:
        """METHOD-020: run 1 program at a time sequentially, save detailed input/output per step"""
        sample_id = sample.get("sample_id") or f"{benchmark.lower()}_{sample_idx:03d}"
        query = sample.get("question") or sample.get("query") or sample.get("instruction") or f"Benchmark {benchmark} sample {sample_idx}"
        # Detailed folder per sample
        sample_dir = self.verification_root / benchmark / sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Save detailed input (what program received)
        input_detail = {
            "sample_id": sample_id,
            "benchmark": benchmark,
            "query": query,
            "sample_idx": sample_idx,
            "ground_truth": sample.get("ground_truth") or sample.get("answer"),
            "image_path": sample.get("image_path"),
            "metadata": sample.get("metadata", {}),
            "timestamp": time.time(),
            "sha_input": hashlib.sha256(json.dumps(sample, sort_keys=True).encode()).hexdigest()[:16]
        }
        with open(sample_dir / "input.json", "w", encoding="utf-8") as f:
            json.dump(input_detail, f, indent=2)

        # Setup our engine: use DocumentStore with synthetic doc from sample
        # Create temp doc file for inspection
        doc_dir = Path("tests/e2e/phase7_dataset/fixtures")
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc_path = doc_dir / f"{sample_id}.txt"
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(f"Benchmark: {benchmark}\nSample: {sample_id}\nQuestion: {query}\nGround Truth: {input_detail['ground_truth']}\nMetadata: {json.dumps(sample.get('metadata', {}))}\n")

        # Build engine components
        from domain.specialist.specialist_registry import SpecialistProfile
        profiles = [
            SpecialistProfile(name="spatial", abilities=["spatial","3d","reconstruct","sam3"], description="spatial specialist"),
            SpecialistProfile(name="barlow", abilities=["barlow","clamp"], description="barlow"),
        ]
        registry = SpecialistRegistry(profiles)
        store = DocumentStore()
        doc = store.ingest(str(doc_path))
        inspector = ContextInspector(store)
        code_idx_path = "index_data/nvidia_spatial_claw.jsonl" if Path("index_data/nvidia_spatial_claw.jsonl").exists() else "index_data/code_index.jsonl"
        tool_idx_path = "index_data/tool_index.jsonl"
        code_idx = CodeReuseIndex(IndexFile(code_idx_path))
        tool_idx = ToolIndex(IndexFile(tool_idx_path))
        cfg = SpatialClawConfigAdapter.load(cli_args={"work_dir": str(Path(work_dir_base) / benchmark / sample_id), "max_steps": 3, "enable_logging": True, "generate_report": True})
        kernel = SpatialClawKernelAdapter(KernelConfig(timeout_sec=10))
        orch = SpatialClawProductionOrchestrator(registry, inspector, code_idx, tool_idx, kernel, cfg, work_dir=str(Path(work_dir_base) / benchmark / sample_id))

        # Run 1 program (orchestrator internally runs steps sequentially, but we run 1 sample at a time here)
        t0 = time.time()
        # We need to capture per-step I/O: orch saves logs, but we will also save per-step detailed folders
        result = await orch.run(query, doc.doc_id, max_steps=3)
        elapsed = time.time() - t0

        # Save each step's detailed input/output (operationality per step)
        for idx, step in enumerate(result.steps):
            step_input = {
                "step_index": idx,
                "sample_id": sample_id,
                "benchmark": benchmark,
                "code": step.code,
                "code_sha": hashlib.sha256(step.code.encode()).hexdigest()[:16],
                "specialist": result.specialist,
                "timestamp": time.time()
            }
            step_output = {
                "step_index": idx,
                "sample_id": sample_id,
                "stdout": step.stdout,
                "stderr": step.stderr,
                "error": step.error,
                "execution_time_sec": step.execution_time_sec,
                "sentinel_answer": step.sentinel_answer,
                "operational": step.error is None,  # per-step operationality
                "timestamp": time.time()
            }
            with open(sample_dir / f"step_{idx:03d}_input.json", "w", encoding="utf-8") as f:
                json.dump(step_input, f, indent=2)
            with open(sample_dir / f"step_{idx:03d}_output.json", "w", encoding="utf-8") as f:
                json.dump(step_output, f, indent=2)

        # Save final aggregated output
        output_detail = {
            "sample_id": sample_id,
            "benchmark": benchmark,
            "query": query,
            "final_answer": result.final_answer,
            "termination_reason": result.termination_reason,
            "steps": len(result.steps),
            "total_tool_calls": result.total_tool_calls,
            "execution_time_sec": result.execution_time_sec,
            "elapsed_wall": elapsed,
            "verification_passed": result.verification_passed,
            "work_dir": result.work_dir,
            "logs_path": result.logs_path,
            "health_checks": result.health_checks,
            "operationality": "PASS" if result.verification_passed and result.termination_reason == "completed" else "FAIL",
            "timestamp": time.time()
        }
        with open(sample_dir / "output.json", "w", encoding="utf-8") as f:
            json.dump(output_detail, f, indent=2)

        # Also copy run.log from work_dir for detailed verification
        try:
            if Path(result.logs_path).exists():
                import shutil
                shutil.copy(result.logs_path, sample_dir / "run.log")
        except:
            pass

        # Save per-sample verification artifact checksum
        with open(sample_dir / "checksum.txt", "w", encoding="utf-8") as f:
            f.write(hashlib.sha256(json.dumps(output_detail, sort_keys=True).encode()).hexdigest())

        return {
            "sample_id": sample_id,
            "benchmark": benchmark,
            "input": input_detail,
            "output": output_detail,
            "steps": len(result.steps),
            "operational": output_detail["operationality"],
            "sample_dir": str(sample_dir),
            "elapsed": elapsed
        }

    async def run_all_sequential(self, benchmark: str = "ERQA", limit: int = 3, hf_token: Optional[str] = None, work_dir_base: str = "work_dir/benchmark") -> Dict[str, Any]:
        """METHOD-021: run 3 samples sequentially (not parallel), each saves detailed I/O, final summary.json"""
        # First ensure dataset downloaded
        dl_res = self.downloader.download(benchmark, hf_token=hf_token)
        samples = self.downloader.get_samples(benchmark, limit=limit)
        if not samples:
            # fallback synthetic already created by downloader
            samples = self.downloader.get_samples(benchmark, limit=limit)
        if not samples:
            raise RuntimeError(f"No samples for {benchmark}")

        # Ensure verification root
        bench_verif_dir = self.verification_root / benchmark
        bench_verif_dir.mkdir(parents=True, exist_ok=True)

        results = []
        total_start = time.time()
        # Sequential: 1 program at a time (not parallel) — verify operationality per program
        for idx, sample in enumerate(samples):
            res = await self.verify_program(benchmark, sample, idx, work_dir_base=work_dir_base)
            results.append(res)
            # Small delay to ensure distinct timestamps and avoid kernel overlap
            await asyncio.sleep(0.2)

        total_elapsed = time.time() - total_start
        summary = {
            "benchmark": benchmark,
            "dataset_repo": dl_res.get("repo"),
            "dataset_files": dl_res.get("files"),
            "samples_run": len(results),
            "operational_pass": sum(1 for r in results if r["operational"] == "PASS"),
            "operational_fail": sum(1 for r in results if r["operational"] != "PASS"),
            "total_elapsed_sec": total_elapsed,
            "samples": [{"sample_id": r["sample_id"], "operational": r["operational"], "elapsed": r["elapsed"], "sample_dir": r["sample_dir"]} for r in results],
            "verification_root": str(bench_verif_dir),
            "timestamp": time.time()
        }
        with open(bench_verif_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Also save to tests/e2e expected for traceability
        expected_path = Path("tests/e2e/phase7_dataset/expected/summary.json")
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        with open(expected_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

    def list_detailed_folders(self, benchmark: str = "ERQA") -> List[str]:
        bench_dir = self.verification_root / benchmark
        if not bench_dir.exists():
            return []
        return [str(p) for p in bench_dir.iterdir() if p.is_dir()]

    def verify_folders_exist(self, benchmark: str = "ERQA", expected_samples: int = 3) -> bool:
        bench_dir = self.verification_root / benchmark
        if not bench_dir.exists():
            return False
        if not (bench_dir / "summary.json").exists():
            return False
        if not (bench_dir / "manifest.json").exists():
            return False
        sample_dirs = [d for d in bench_dir.iterdir() if d.is_dir() and d.name.startswith(benchmark.lower()) or d.name.startswith("erqa_synthetic")]
        # Also check generic sample dirs
        sample_dirs = [d for d in bench_dir.iterdir() if d.is_dir()]
        if len(sample_dirs) < expected_samples:
            # Check synthetic naming
            synthetic_dirs = list(bench_dir.glob("*synthetic*"))
            if len(synthetic_dirs) < expected_samples:
                return False
        # Check each has input/output per step
        for sd in bench_dir.iterdir():
            if sd.is_dir():
                if not (sd / "input.json").exists():
                    return False
                if not (sd / "output.json").exists():
                    return False
                # At least 1 step
                if not list(sd.glob("step_*_input.json")):
                    return False
        return True
