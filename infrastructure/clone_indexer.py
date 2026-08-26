"""FILE-014: clone and index external repo — must never decide specialty"""
import os
import subprocess
import hashlib
import json
from typing import List
from pathlib import Path

class CloneIndexer:
    """SRP: clone and index external repo"""

    def clone_repo(self, url: str, dest: str) -> str:
        """METHOD-012: clone into isolated cloning/ folder"""
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        if os.path.exists(dest) and os.listdir(dest):
            # idempotent: already cloned, pull not needed for verification (avoid network side-effect duplication)
            return dest
        result = subprocess.run(["git", "clone", "--depth", "1", url, dest], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr}")
        return dest

    def index_external_code(self, source_dir: str, index_path: str, pattern: str = "*.py", max_files: int = 200) -> int:
        """METHOD-013: walk source, hash, append to index_data/ (not LLM context)"""
        from domain.index.index_file import IndexFile
        idx = IndexFile(index_path)
        # ensure idempotent: clear or dedup via hash inside CodeReuseIndex logic, here we just append
        count = 0
        for p in Path(source_dir).rglob(pattern):
            if count >= max_files:
                break
            if p.stat().st_size > 20000:
                continue
            try:
                code = p.read_text(encoding="utf-8", errors="ignore")
            except:
                continue
            if len(code.strip()) < 20:
                continue
            h = hashlib.md5(code.encode()).hexdigest()[:12]
            # dedup check
            existing = [e for e in idx.read_all() if e.get("hash") == h]
            if existing:
                continue
            idx.append({"hash": h, "code": code[:4000], "description": f"external:{p.relative_to(source_dir)}", "use_count": 0})
            count += 1
        return count

    def search_external(self, index_path: str, query: str, top_k: int = 3) -> List[dict]:
        """METHOD-014: search indexed external code without loading full repo"""
        from domain.index.code_reuse_index import CodeReuseIndex, SearchQuery
        from domain.index.index_file import IndexFile
        idx = CodeReuseIndex(IndexFile(index_path))
        hits = idx.search(SearchQuery(text=query, top_k=top_k))
        return [{"description": h.snippet.description, "score": h.score, "code_preview": h.snippet.code[:200]} for h in hits]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Clone and index external repo")
    ap.add_argument("--source", help="if url, clone dest; if local path, just index")
    ap.add_argument("--url", help="git url to clone")
    ap.add_argument("--dest", default="cloning/special-flower", help="clone dest folder")
    ap.add_argument("--index", default="index_data/external_code.jsonl")
    ap.add_argument("--query", help="test search query after index")
    args = ap.parse_args()
    ci = CloneIndexer()
    if args.url:
        print(f"Cloning {args.url} -> {args.dest}")
        ci.clone_repo(args.url, args.dest)
    src = args.source or args.dest
    if os.path.exists(src):
        n = ci.index_external_code(src, args.index)
        print(f"Indexed {n} files -> {args.index}")
        if args.query:
            print(ci.search_external(args.index, args.query))
