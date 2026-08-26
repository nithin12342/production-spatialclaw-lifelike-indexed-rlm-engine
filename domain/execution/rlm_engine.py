"""FILE-008: recursive spawn and synthesize — must never own tool specs"""
from dataclasses import dataclass, field
from typing import List, Callable, Any, Optional

@dataclass
class SpawnRequest:
    query: str
    context_slice: str
    depth: int

@dataclass
class SynthesisResult:
    answer: str
    depth: int
    children: List["SynthesisResult"] = field(default_factory=list)

class RLMEngine:
    """SRP: recursive spawn and synthesize"""
    def __init__(self, llm_call: Callable, max_depth: int = 3, max_parallel: int = 4):
        self._llm = llm_call
        self.max_depth = max_depth
        self.max_parallel = max_parallel

    async def spawn(self, query: str, context: str, depth: int = 0) -> SynthesisResult:
        """METHOD-009: chunk+parallel spawn if large, else direct"""
        import asyncio
        # leaf if shallow or small context
        if depth >= self.max_depth or len(context) < 4000:
            res = await self._llm(query, context[:4000])
            # normalize llm result to str
            ans = res if isinstance(res, str) else str(res)
            return SynthesisResult(answer=ans, depth=depth, children=[])
        # chunk large context (~4000 char chunks) and spawn parallel children
        chunk_size = 4000
        chunks = [context[i:i+chunk_size] for i in range(0, len(context), chunk_size)]
        chunks = chunks[:self.max_parallel]  # cap parallelism
        # parallel spawn
        tasks = []
        for idx, chunk in enumerate(chunks):
            child_q = f"[sub {idx+1}/{len(chunks)}] {query} | focus only on this chunk"
            tasks.append(self.spawn(child_q, chunk, depth+1))
        children = await asyncio.gather(*tasks)
        # synthesis: feed child answers to llm
        synth_ctx = "\n\n".join([f"--- child {i} ---\n{c.answer[:800]}" for i, c in enumerate(children)])
        final = await self._llm(f"Synthesize {len(children)} sub-results for: {query}", synth_ctx[:8000])
        final_ans = final if isinstance(final, str) else str(final)
        return SynthesisResult(answer=final_ans, depth=depth, children=list(children))
