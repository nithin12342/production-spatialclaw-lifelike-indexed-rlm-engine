"""FILE-020: expose production CLI — must never contain business logic"""
import asyncio
import argparse
import os
from typing import Optional

class ProductionCLI:
    """SRP: expose production CLI"""

    def run(self, query: str, doc_path: str, work_dir: str = "work_dir/production") -> None:
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from domain.specialist.specialist_registry import SpecialistRegistry, SpecialistProfile
        from domain.inspection.document_store import DocumentStore
        from domain.inspection.context_inspector import ContextInspector
        from domain.index.index_file import IndexFile
        from domain.index.code_reuse_index import CodeReuseIndex
        from domain.index.tool_index import ToolIndex
        from infrastructure.spatial_claw_config_adapter import SpatialClawConfigAdapter
        from infrastructure.spatial_claw_kernel_adapter import SpatialClawKernelAdapter, KernelConfig
        from application.integration.spatial_claw_production import SpatialClawProductionOrchestrator

        async def _run():
            profiles = [
                SpecialistProfile(name="spatial", abilities=["spatial","3d","reconstruct","sam3"], description="spatial reconstruction specialist"),
                SpecialistProfile(name="barlow", abilities=["barlow","clamp"], description="barlow twins"),
            ]
            registry = SpecialistRegistry(profiles)
            store = DocumentStore()
            doc = store.ingest(doc_path)
            inspector = ContextInspector(store)
            code_idx = CodeReuseIndex(IndexFile("index_data/nvidia_spatial_claw.jsonl" if os.path.exists("index_data/nvidia_spatial_claw.jsonl") else "index_data/code_index.jsonl"))
            tool_idx = ToolIndex(IndexFile("index_data/tool_index.jsonl"))
            config = SpatialClawConfigAdapter.load(cli_args={"work_dir": work_dir}, model_json=None, dataset_json=None)
            kernel = SpatialClawKernelAdapter(KernelConfig(timeout_sec=config.timeout_sec))
            orch = SpatialClawProductionOrchestrator(registry, inspector, code_idx, tool_idx, kernel, config, work_dir=work_dir)
            result = await orch.run(query, doc.doc_id, max_steps=5)
            print(f"PRODUCTION RESULT: specialist={result.specialist} termination={result.termination_reason} steps={len(result.steps)} answer={result.final_answer} verified={result.verification_passed} logs={result.logs_path}")
            print(f"Health: {result.health_checks}")
        asyncio.run(_run())

def main():
    ap = argparse.ArgumentParser(description="Production SpatialClaw + Lifelike Engine CLI")
    ap.add_argument("query", help="Query")
    ap.add_argument("doc_path", help="Document path")
    ap.add_argument("--work-dir", default="work_dir/production")
    args = ap.parse_args()
    ProductionCLI().run(args.query, args.doc_path, args.work_dir)

if __name__ == "__main__":
    main()
