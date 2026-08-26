"""FILE-011: sqlite index file persistence — must never decide search ranking"""
import sqlite3
import json
from typing import List, Dict, Any
from domain.index.index_file import IndexFileRef

class IndexStore:
    """SRP: sqlite index file persistence"""
    def __init__(self, db_path: str):
        self.db_path = db_path

    def init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS code_snippets (hash TEXT PRIMARY KEY, code TEXT, description TEXT, use_count INTEGER)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS tool_index (name TEXT PRIMARY KEY, description TEXT, parameters TEXT, code_ref TEXT)""")
        conn.commit()
        conn.close()

    def append(self, table: str, entry: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        if table == "code_snippets":
            cur.execute("INSERT OR IGNORE INTO code_snippets (hash, code, description, use_count) VALUES (?,?,?,?)",
                        (entry["hash"], entry["code"], entry["description"], entry.get("use_count", 0)))
        elif table == "tool_index":
            cur.execute("INSERT OR REPLACE INTO tool_index (name, description, parameters, code_ref) VALUES (?,?,?,?)",
                        (entry["name"], entry["description"], json.dumps(entry.get("parameters", {})), entry.get("code_ref", "")))
        else:
            raise ValueError(f"unknown table {table}")
        conn.commit()
        conn.close()

    def search_like(self, table: str, query: str, top_k: int) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # get all, ranking done in Python via EmbeddingSearch (keeps SQL simple and deterministic)
        if table == "code_snippets":
            cur.execute("SELECT hash, code, description, use_count FROM code_snippets")
        elif table == "tool_index":
            cur.execute("SELECT name, description, parameters, code_ref FROM tool_index")
        else:
            raise ValueError(table)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        # caller will rank; return all for now (but E2E will verify we only load top_k into context)
        return rows

    def get_by_name(self, table: str, name: str) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if table == "tool_index":
            cur.execute("SELECT name, description, parameters, code_ref FROM tool_index WHERE name=?", (name,))
        elif table == "code_snippets":
            cur.execute("SELECT hash, code, description, use_count FROM code_snippets WHERE hash=?", (name,))
        else:
            raise ValueError(table)
        row = cur.fetchone()
        conn.close()
        if row is None:
            raise KeyError(f"not found {table}:{name}")
        d = dict(row)
        if "parameters" in d and isinstance(d["parameters"], str):
            try:
                d["parameters"] = json.loads(d["parameters"])
            except:
                pass
        return d
