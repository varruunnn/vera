from dataclasses import dataclass, field
from typing import Optional, List
from vera.core.evidence import DecisionEvidenceSet
from vera.core.models import Action

@dataclass
class ActionIntent:
    audience: str
    action_type: str
    merchant_id: str
    trigger_id: str
    customer_id: Optional[str] = None
    suppression_key: Optional[str] = None

@dataclass
class MessageStrategy:
    audience: str
    purpose: str
    tone: str
    key_points: List[str]
    allowed_claims: List[str]
    prohibited_claims: List[str]
    cta: str

@dataclass
class Decision:
    should_act: bool
    reason: str
    evidence: DecisionEvidenceSet
    intent: Optional[ActionIntent] = None
    strategy: Optional[MessageStrategy] = None
    output_action: Optional[Action] = None
