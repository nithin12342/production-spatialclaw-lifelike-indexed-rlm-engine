"""FILE-013: expose programmatic call CLI — must never contain business logic"""
import asyncio
import argparse
from typing import Any

class CLI:
    """SRP: expose programmatic call CLI"""
    def run(self, query: str, doc_path: str) -> None:
        import asyncio
        from domain.specialist.specialist_registry import SpecialistRegistry, SpecialistProfile
        from domain.inspection.document_store import DocumentStore
        from domain.inspection.context_inspector import ContextInspector
        from domain.index.index_file import IndexFile
        from domain.index.code_reuse_index import CodeReuseIndex
        from domain.index.tool_index import ToolIndex
        from domain.execution.rlm_engine import RLMEngine
        from domain.execution.speculative_executor import SpeculativeExecutor
        from application.programmatic_call import ProgrammaticCall

        async def _run():
            profiles = [
                SpecialistProfile(name="barlow", abilities=["barlow", "clamp", "fp16"], description="barlow twins fp16 clamp specialist"),
                SpecialistProfile(name="viz", abilities=["viz", "plot"], description="visualization"),
                SpecialistProfile(name="ntp", abilities=["ntp", "token"], description="next token prediction"),
            ]
            registry = SpecialistRegistry(profiles)
            store = DocumentStore()
            doc = store.ingest(doc_path)
            inspector = ContextInspector(store)
            code_idx = CodeReuseIndex(IndexFile("index_data/code_index.jsonl"))
            tool_idx = ToolIndex(IndexFile("index_data/tool_index.jsonl"))
            async def mock_llm(p, c=""): await asyncio.sleep(0.02); return f"[{p[:40]}...]"
            rlm = RLMEngine(mock_llm, max_depth=2)
            spec = SpeculativeExecutor()
            call = ProgrammaticCall(registry, inspector, code_idx, tool_idx, rlm, spec)
            res = await call.execute(query, doc.doc_id, mock_llm)
            print(f"Answer: {res.answer}\nSpecialist: {res.specialist} RLM depth: {res.rlm_depth} hits: {res.speculative_hits} tools: {res.tools_used} tokens: {res.index_search_tokens} verified: {res.verification_passed}")

        asyncio.run(_run())

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Lifelike Indexed Programmatic Call CLI")
    ap.add_argument("query", help="query text")
    ap.add_argument("doc_path", help="document path")
    args = ap.parse_args()
    CLI().run(args.query, args.doc_path)

if __name__ == "__main__":
    main()
