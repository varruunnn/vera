from dataclasses import dataclass
from typing import Optional
from vera.core.evidence import EvidenceSet
from vera.core.models import Action

@dataclass
class ActionIntent:
    audience: str
    action_type: str
    merchant_id: str
    trigger_id: str
    customer_id: Optional[str] = None
    template_name: Optional[str] = None
    template_params: Optional[list[str]] = None
    body: Optional[str] = None
    cta: Optional[str] = None
    suppression_key: Optional[str] = None

@dataclass
class Decision:
    should_act: bool
    reason: str
    evidence: EvidenceSet
    intent: Optional[ActionIntent] = None
    output_action: Optional[Action] = None
