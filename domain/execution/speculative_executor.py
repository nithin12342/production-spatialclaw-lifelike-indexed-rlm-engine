"""FILE-009: speculative pre-execute and commit — must never speculate unsafe writes"""
from dataclasses import dataclass
from typing import List, Dict, Any
import asyncio

@dataclass
class SpeculativeTask:
    tool: str
    args: Dict[str, Any]
    confidence: float

@dataclass
class CommittedResult:
    tool: str
    result: Any
    hit: bool

class SpeculativeExecutor:
    """SRP: speculative pre-execute and commit"""
    def __init__(self, threshold: float = 0.55, max_parallel: int = 6):
        self.threshold = threshold
        self.max_parallel = max_parallel
        self._cache: Dict[str, Any] = {}

    async def speculate(self, predicted: List[SpeculativeTask]) -> Dict[str, asyncio.Task]:
        import hashlib, json
        candidates = [p for p in predicted if p.confidence >= self.threshold]
        candidates = sorted(candidates, key=lambda x: x.confidence, reverse=True)[:self.max_parallel]
        tasks: Dict[str, asyncio.Task] = {}
        for pred in candidates:
            # only speculative_safe assumed; caller filters unsafe
            key = hashlib.md5(f"{pred.tool}:{json.dumps(pred.args, sort_keys=True)}".encode()).hexdigest()
            if key in self._cache:
                continue
            # need a dummy executor: for demo, just echo; real will be injected
            async def _exec(tool=pred.tool, args=pred.args):
                await asyncio.sleep(0.02)
                return {"tool": tool, "args": args, "result": f"spec_result_{tool}"}
            tasks[key] = asyncio.create_task(_exec())
        return tasks

    async def commit(self, final_calls: List[Dict[str, Any]], speculative_tasks: Dict[str, asyncio.Task]) -> List[CommittedResult]:
        """METHOD-010: hit reuse, miss execute, abort unused"""
        import hashlib, json
        results: List[CommittedResult] = []
        for call in final_calls:
            tool = call.get("tool") or call.get("name")
            args = call.get("args") or call.get("arguments") or {}
            key = hashlib.md5(f"{tool}:{json.dumps(args, sort_keys=True)}".encode()).hexdigest()
            if key in speculative_tasks:
                try:
                    res = await speculative_tasks[key]
                    self._cache[key] = res
                    results.append(CommittedResult(tool=tool, result=res, hit=True))
                except asyncio.CancelledError:
                    results.append(CommittedResult(tool=tool, result={"error": "cancelled"}, hit=False))
            elif key in self._cache:
                results.append(CommittedResult(tool=tool, result=self._cache[key], hit=True))
            else:
                # miss: execute now
                await asyncio.sleep(0.02)
                res = {"tool": tool, "args": args, "result": f"direct_{tool}"}
                self._cache[key] = res
                results.append(CommittedResult(tool=tool, result=res, hit=False))
        # abort unused
        committed_keys = {hashlib.md5(f"{(c.get('tool') or c.get('name'))}:{json.dumps((c.get('args') or c.get('arguments') or {}), sort_keys=True)}".encode()).hexdigest() for c in final_calls}
        for k, t in list(speculative_tasks.items()):
            if k not in committed_keys:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        return results
