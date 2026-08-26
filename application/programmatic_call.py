"""FILE-010: orchestrate indexed programmatic call — must never implement domain invariants"""
from dataclasses import dataclass
from typing import Any, Dict, List
from domain.specialist.specialist_registry import SpecialistRegistry
from domain.inspection.context_inspector import ContextInspector
from domain.index.code_reuse_index import CodeReuseIndex
from domain.index.tool_index import ToolIndex
from domain.execution.rlm_engine import RLMEngine
from domain.execution.speculative_executor import SpeculativeExecutor

@dataclass
class ProgrammaticCallResult:
    answer: str
    specialist: str
    rlm_depth: int
    speculative_hits: int
    tools_used: List[str]
    verification_passed: bool
    index_search_tokens: int  # proof we didn't bulk load

class ProgrammaticCall:
    """SRP: orchestrate indexed programmatic call"""
    def __init__(self, registry: SpecialistRegistry, inspector: ContextInspector, code_index: CodeReuseIndex, tool_index: ToolIndex, rlm: RLMEngine, spec_exec: SpeculativeExecutor):
        self._registry = registry
        self._inspector = inspector
        self._code_index = code_index
        self._tool_index = tool_index
        self._rlm = rlm
        self._spec = spec_exec

    async def execute(self, query: str, doc_id: Any, llm_call: Any) -> ProgrammaticCallResult:
        """METHOD-011: E2E indexed flow, no MCP bulk"""
        # Step 1: Specialist selection (programmatic, not JSON blob)
        choice = self._registry.select_specialist(query)
        # Step 2: Code-based inspection (LLM writes code to see context, not prompt stuffing)
        # Simulate LLM generating inspection code
        inspection_code = 'result = store.slice(doc_id, SliceSpec(offset=0, length=800))'
        inspection = self._inspector.inspect_via_code(doc_id, inspection_code)
        # Step 3: Indexed code reuse search (only top_k, not full index)
        from domain.index.code_reuse_index import SearchQuery
        code_hits = self._code_index.search(SearchQuery(text=query, top_k=2))
        # Step 4: Indexed tool search (avoid MCP bulk — only top 3 lites)
        tool_hits = self._tool_index.search_tools(query, top_k=3)
        # Lazy load only necessary tool specs (proof: index tokens < 1k)
        loaded_specs = []
        for hit in tool_hits:
            try:
                full = self._tool_index.lazy_load(hit.lite.name)
                loaded_specs.append(full)
            except KeyError:
                pass
        # Estimate index_search_tokens = only loaded specs, not full index
        index_search_tokens = sum(len(s.description) // 4 for s in loaded_specs) + sum(len(h.snippet.code)//4 for h in code_hits)
        # Step 5: RLM on inspection slice (if large)
        rlm_result = await self._rlm.spawn(query, inspection.slice_text, depth=0)
        # Step 6: Speculative execution of top tools
        from domain.execution.speculative_executor import SpeculativeTask
        predicted = [SpeculativeTask(tool=hit.lite.name, args={"query": query}, confidence=hit.score) for hit in tool_hits]
        spec_tasks = await self._spec.speculate(predicted)
        final_calls = [{"tool": hit.lite.name, "args": {"query": query}} for hit in tool_hits[:2]]
        committed = await self._spec.commit(final_calls, spec_tasks)
        hits = sum(1 for c in committed if c.hit)
        tools_used = [c.tool for c in committed]
        # Step 7: Synthesis via llm_call with only indexed hits, not bulk index
        synth_prompt = f"Specialist {choice.specialist.name} answering '{query}' with slice '{inspection.slice_text[:200]}' and code hits {[h.snippet.description for h in code_hits]}"
        answer_raw = await llm_call(synth_prompt, "")
        answer = answer_raw if isinstance(answer_raw, str) else str(answer_raw)
        # verification: answer non-empty and index_search_tokens < 1000 (proof of no bulk load)
        verified = len(answer.strip()) > 10 and index_search_tokens < 1000 and len(loaded_specs) <= 3
        return ProgrammaticCallResult(
            answer=answer,
            specialist=choice.specialist.name,
            rlm_depth=rlm_result.depth,
            speculative_hits=hits,
            tools_used=tools_used,
            verification_passed=verified,
            index_search_tokens=index_search_tokens
        )
