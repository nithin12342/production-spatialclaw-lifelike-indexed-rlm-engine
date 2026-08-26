"""FILE-012: vector search over index — must never mutate index"""
from typing import List, Dict, Any, Tuple
import math

class EmbeddingSearch:
    """SRP: vector search over index"""
    def __init__(self):
        pass

    def score(self, query: str, doc: str) -> float:
        """Simple lexical overlap + TF-like score (no external deps, deterministic)"""
        q_tokens = query.lower().split()
        d_lower = doc.lower()
        if not q_tokens:
            return 0.0
        # overlap
        overlap = sum(1 for tok in q_tokens if tok in d_lower)
        # boost exact phrase
        phrase_bonus = 2.0 if query.lower() in d_lower else 0.0
        # length normalization
        score = (overlap / len(q_tokens)) + phrase_bonus
        # TF-like: rare token bonus (inverse length)
        score = score / (1 + math.log1p(len(d_lower) / 500))
        return round(float(score), 4)

    def top_k(self, query: str, docs: List[Dict[str, Any]], k: int, text_key: str = "code") -> List[Tuple[Dict[str, Any], float]]:
        scored = []
        for d in docs:
            txt = d.get(text_key, "") if isinstance(d, dict) else str(d)
            if isinstance(txt, dict):
                txt = str(txt)
            s = self.score(query, str(txt))
            scored.append((d, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
