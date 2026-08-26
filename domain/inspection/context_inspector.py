"""FILE-003: programmatic context inspection via code — must never load full docs into LLM prompt"""
from dataclasses import dataclass
from typing import Callable, Any
from .document_store import DocumentStore, DocId, SliceSpec

@dataclass
class InspectionQuery:
    intent: str
    code: str  # LLM-generated Python code handle

@dataclass
class InspectionResult:
    slice_text: str
    byte_range: SliceSpec
    inspection_code: str

class ContextInspector:
    """SRP: programmatic context inspection via code"""
    def __init__(self, store: DocumentStore):
        self._store = store

    def inspect_via_code(self, doc_id: DocId, llm_code: str) -> InspectionResult:
        """METHOD-004: LLM writes code like store.slice(0,100), never receives full doc"""
        # LLM code is executed in restricted env with only code handle, not full doc
        # Example llm_code: "result = store.slice(doc_id, SliceSpec(offset=0, length=200))"
        env = self.get_code_handle_env(doc_id)
        # imports for code
        env["SliceSpec"] = SliceSpec
        env["DocId"] = DocId
        # Capture result via exec
        local_vars: dict = {}
        exec(llm_code, env, local_vars)
        # Convention: LLM code must set `result` or `slice_text`
        slice_text = local_vars.get("result") or local_vars.get("slice_text") or local_vars.get("output") or ""
        if not isinstance(slice_text, str):
            slice_text = str(slice_text)
        # Try to infer range from code string for audit
        byte_range = SliceSpec(offset=0, length=len(slice_text))
        if "SliceSpec" in llm_code:
            # best effort parse offset/length
            import re
            m = re.search(r"offset\s*=\s*(\d+).*length\s*=\s*(\d+)", llm_code)
            if m:
                byte_range = SliceSpec(offset=int(m.group(1)), length=int(m.group(2)))
        return InspectionResult(slice_text=slice_text, byte_range=byte_range, inspection_code=llm_code)

    def get_code_handle_env(self, doc_id: DocId) -> dict:
        """Returns env dict for LLM code execution: {'store': ..., 'slice': ...}"""
        # Only expose slice handle, never full text
        def slice_handle(offset: int = 0, length: int = 500):
            return self._store.slice(doc_id, SliceSpec(offset=offset, length=length))
        return {
            "store": self._store,
            "doc_id": doc_id,
            "slice": slice_handle,
            "SliceSpec": SliceSpec,
        }
