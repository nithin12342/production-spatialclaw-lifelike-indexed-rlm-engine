"""FILE-007: persist index file on disk — must never do semantic ranking"""
from dataclasses import dataclass
from typing import List, Dict, Any
import os

@dataclass
class IndexFileRef:
    path: str
    entry_count: int

class IndexFile:
    """SRP: persist index file on disk"""
    def __init__(self, path: str):
        self.path = path
        # ensure file exists
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        if not os.path.exists(path):
            open(path, "a").close()

    def append(self, entry: Dict[str, Any]) -> None:
        import json
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def read_all(self) -> List[Dict[str, Any]]:
        import json
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            return []
        out = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def size_bytes(self) -> int:
        if not os.path.exists(self.path):
            return 0
        return os.path.getsize(self.path)
