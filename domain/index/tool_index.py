"""FILE-006: indexed tool search, lazy load — must never expose full index to LLM"""
from dataclasses import dataclass
from typing import List, Dict, Any
from .index_file import IndexFile

@dataclass
class ToolSpecLite:
    name: str
    description: str
    relevance: float

@dataclass
class ToolSpecFull:
    name: str
    description: str
    parameters: Dict[str, Any]
    code_ref: str

@dataclass
class SearchResult:
    lite: ToolSpecLite
    score: float

class ToolIndex:
    """SRP: indexed tool search, lazy load"""
    def __init__(self, index_file: IndexFile):
        self._file = index_file

    def search_tools(self, query: str, top_k: int = 3) -> List[SearchResult]:
        """METHOD-007: only top-k lites, not 50; index stays on disk"""
        all_entries = self._file.read_all()
        # IMPORTANT: index file stays on disk; we only return top_k lite specs to LLM context
        # not the full 50. This avoids MCP window filling.
        q = query.lower()
        scored = []
        for e in all_entries:
            txt = (e.get("name","") + " " + e.get("description","")).lower()
            score = 0.0
            for tok in q.split():
                if tok in txt:
                    score += 1.0
            if q in txt:
                score += 1.5
            score = score / max(1, len(q.split()))
            scored.append((e, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for e, s in scored[:top_k]:
            # lite: only name+desc, not full parameters (lazy)
            lite = ToolSpecLite(name=e["name"], description=e["description"][:120], relevance=round(s,3))
            results.append(SearchResult(lite=lite, score=round(s,3)))
        return results

    def lazy_load(self, tool_name: str) -> ToolSpecFull:
        """METHOD-008: load full spec from disk on demand"""
        for e in self._file.read_all():
            if e.get("name") == tool_name:
                return ToolSpecFull(name=e["name"], description=e["description"], parameters=e.get("parameters", {}), code_ref=e.get("code_ref",""))
        raise KeyError(f"tool not found: {tool_name}")

    def register_tool(self, spec: ToolSpecFull) -> None:
        self._file.append({"name": spec.name, "description": spec.description, "parameters": spec.parameters, "code_ref": spec.code_ref})
