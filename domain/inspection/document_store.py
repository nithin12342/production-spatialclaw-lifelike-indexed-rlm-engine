"""FILE-004: store and slice documents — must never call LLM"""
from dataclasses import dataclass
from typing import Dict
import os

@dataclass
class DocId:
    value: str

@dataclass
class SliceSpec:
    offset: int
    length: int

class Document:
    def __init__(self, doc_id: DocId, path: str, byte_count: int):
        self.doc_id = doc_id
        self.path = path
        self.byte_count = byte_count

class DocumentStore:
    """SRP: store and slice documents"""
    def __init__(self):
        self._docs: Dict[str, Document] = {}

    def ingest(self, path: str) -> Document:
        """METHOD-003: ingest real file, byte count matches"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Document not found: {path}")
        byte_count = os.path.getsize(path)
        # read to validate
        with open(path, "rb") as f:
            _ = f.read()
        doc_id = DocId(value=os.path.abspath(path))
        doc = Document(doc_id=doc_id, path=os.path.abspath(path), byte_count=byte_count)
        self._docs[doc_id.value] = doc
        return doc

    def slice(self, doc_id: DocId, spec: SliceSpec) -> str:
        doc = self._docs.get(doc_id.value)
        if doc is None:
            raise KeyError(f"doc not ingested: {doc_id.value}")
        with open(doc.path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return text[spec.offset: spec.offset + spec.length]

    def byte_count(self, doc_id: DocId) -> int:
        doc = self._docs.get(doc_id.value)
        if doc is None:
            raise KeyError(doc_id.value)
        return doc.byte_count
