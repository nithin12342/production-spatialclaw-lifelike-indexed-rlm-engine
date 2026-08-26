"""FILE-005: index and search code snippets — must never bulk-load into context"""
from dataclasses import dataclass
from typing import List, Optional
import hashlib
from .index_file import IndexFile

@dataclass
class CodeSnippet:
    hash: str
    code: str
    description: str
    use_count: int = 0

@dataclass
class SearchQuery:
    text: str
    top_k: int = 3

@dataclass
class SnippetHit:
    snippet: CodeSnippet
    score: float

class CodeReuseIndex:
    """SRP: index and search code snippets"""
    def __init__(self, index_file: IndexFile):
        self._file = index_file

    def index_code(self, code: str, description: str) -> CodeSnippet:
        """METHOD-005: append-only, deduplicate by hash"""
        h = self._hash(code)
        # dedup check: read all, if hash exists return existing
        existing = [e for e in self._file.read_all() if e.get("hash") == h]
        if existing:
            e = existing[0]
            return CodeSnippet(hash=e["hash"], code=e["code"], description=e["description"], use_count=e.get("use_count", 0))
        snippet = CodeSnippet(hash=h, code=code, description=description, use_count=0)
        self._file.append({"hash": h, "code": code, "description": description, "use_count": 0})
        return snippet

    def search(self, query: SearchQuery) -> List[SnippetHit]:
        """METHOD-006: search without loading full index into LLM context"""
        all_entries = self._file.read_all()
        # ranking via lexical score, deterministic, no external deps
        # IMPORTANT: only top_k are returned to caller (LLM context), full index never bulk-loaded
        q = query.text.lower()
        scored = []
        for e in all_entries:
            txt = (e.get("code", "") + " " + e.get("description", "")).lower()
            score = 0.0
            for tok in q.split():
                if tok in txt:
                    score += 1.0
            if q in txt:
                score += 2.0
            # normalize
            score = score / max(1, len(q.split()))
            if score > 0:
                scored.append((e, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        hits = []
        for e, s in scored[:query.top_k]:
            hits.append(SnippetHit(snippet=CodeSnippet(hash=e["hash"], code=e["code"], description=e["description"], use_count=e.get("use_count",0)), score=round(s,3)))
        return hits

    def _hash(self, code: str) -> str:
        return hashlib.md5(code.encode()).hexdigest()[:12]
