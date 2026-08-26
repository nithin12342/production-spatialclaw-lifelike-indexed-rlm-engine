"""FILE-001: rank and select specialist — must never touch index I/O"""
from dataclasses import dataclass
from typing import List

@dataclass
class SpecialistProfile:
    name: str
    abilities: List[str]
    description: str

@dataclass
class AbilityScore:
    specialist: str
    score: float
    reason: str

@dataclass
class SpecialistChoice:
    specialist: SpecialistProfile
    score: AbilityScore
    programmatic_handle: str  # not JSON blob

class SpecialistRegistry:
    """SRP: rank and select specialist"""
    def __init__(self, profiles: List[SpecialistProfile]):
        self._profiles = profiles

    def select_specialist(self, query: str) -> SpecialistChoice:
        """METHOD-001: programmatic specialist selection, not JSON"""
        q = query.lower()
        best = None
        best_score = -1.0
        best_reason = ""
        for p in self._profiles:
            # score = max overlap between query tokens and abilities
            score = 0.0
            matched = []
            for ab in p.abilities:
                if ab.lower() in q or any(tok in ab.lower() for tok in q.split()):
                    score += 1.0
                    matched.append(ab)
            # also token overlap with description
            desc_overlap = sum(1 for tok in q.split() if tok in p.description.lower()) * 0.3
            score += desc_overlap
            # normalize by abilities count, boost exact
            if matched:
                score = score / max(1, len(p.abilities)) + (0.2 if len(matched) > 1 else 0)
            if score > best_score:
                best_score = score
                best = p
                best_reason = f"matched {matched} overlap={score:.2f}"
        if best is None:
            best = self._profiles[0]
            best_score = 0.0
            best_reason = "fallback first"
        # programmatic handle: object reference, not JSON blob (deterministic)
        import hashlib
        h = int(hashlib.md5(best.name.encode()).hexdigest()[:4], 16)
        handle = f"specialist://{best.name}#{h:04x}"
        return SpecialistChoice(
            specialist=best,
            score=AbilityScore(specialist=best.name, score=float(best_score), reason=best_reason),
            programmatic_handle=handle
        )
