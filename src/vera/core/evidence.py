from dataclasses import dataclass, field
from typing import Any, Literal, List, Optional
from vera.core.models import ContextPayload

EvidenceKind = Literal["RAW_FACT", "DERIVED_FACT", "RECOMMENDATION"]

@dataclass
class Evidence:
    kind: EvidenceKind
    value: Any
    source_domain: str
    source_id: str
    field_path: str
    explanation: str

class DecisionEvidenceSet:
    def __init__(self):
        self.items: List[Evidence] = []

    def add(self, evidence: Evidence):
        self.items.append(evidence)

    def get_by_kind(self, kind: EvidenceKind) -> List[Evidence]:
        return [e for e in self.items if e.kind == kind]

    def get_by_domain(self, domain: str) -> List[Evidence]:
        return [e for e in self.items if e.source_domain == domain]

    def to_dict(self) -> List[dict]:
        return [
            {
                "kind": e.kind,
                "domain": e.source_domain,
                "id": e.source_id,
                "field": e.field_path,
                "value": e.value
            }
            for e in self.items
        ]
