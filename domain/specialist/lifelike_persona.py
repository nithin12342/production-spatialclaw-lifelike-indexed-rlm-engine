"""FILE-002: render lifelike persona traits — must never decide routing"""
from dataclasses import dataclass
from typing import List
from .specialist_registry import SpecialistChoice

@dataclass
class Trait:
    name: str
    intensity: float

@dataclass
class Voice:
    tone: str
    cadence: str

@dataclass
class Persona:
    specialist_name: str
    traits: List[Trait]
    voice: Voice

class LifelikePersona:
    """SRP: render lifelike persona traits"""
    def render(self, choice: SpecialistChoice) -> Persona:
        """METHOD-002: pure data rendering, no I/O"""
        # Deterministic persona from specialist name hash, no I/O (idempotent)
        import hashlib
        name = choice.specialist.name
        h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
        traits_pool = [
            ("precise", 0.9), ("curious", 0.8), ("calm", 0.85),
            ("analytical", 0.92), ("empathetic", 0.75), ("decisive", 0.88),
            ("meticulous", 0.90), ("adaptive", 0.82)
        ]
        traits = []
        for i in range(3):
            idx = (h + i * 7) % len(traits_pool)
            t_name, base = traits_pool[idx]
            traits.append(Trait(name=t_name, intensity=round(base - (i*0.05), 2)))
        tones = ["measured", "warm", "crisp", "thoughtful"]
        cadences = ["steady", "fluid", "deliberate", "lively"]
        voice = Voice(tone=tones[h % len(tones)], cadence=cadences[(h // 7) % len(cadences)])
        return Persona(specialist_name=name, traits=traits, voice=voice)
