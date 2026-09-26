from dataclasses import dataclass
from typing import Any, Literal

@dataclass
class Evidence:
    kind: Literal["raw_fact", "derived_fact", "recommendation"]
    value: Any
    source_domain: str
    source_id: str
    field_path: str
    explanation: str

class EvidenceSet:
    def __init__(self):
        self.items: list[Evidence] = []
        
    def add(self, evidence: Evidence):
        self.items.append(evidence)
        
    def get_by_kind(self, kind: str) -> list[Evidence]:
        return [e for e in self.items if e.kind == kind]
        
    def get_by_domain(self, domain: str) -> list[Evidence]:
        return [e for e in self.items if e.source_domain == domain]
