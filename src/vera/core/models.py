from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

class Scope(str, Enum):
    CATEGORY = "category"
    MERCHANT = "merchant"
    CUSTOMER = "customer"
    TRIGGER = "trigger"

class CategoryContext(BaseModel):
    category_id: str
    name: str
    vocabulary: Optional[List[str]] = None
    model_config = ConfigDict(extra='allow')

class MerchantContext(BaseModel):
    merchant_id: str
    name: str
    category_id: Optional[str] = None
    performance: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(extra='allow')

class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    name: str
    preferences: Optional[Dict[str, Any]] = None
    history: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(extra='allow')

class TriggerContext(BaseModel):
    id: str
    kind: str
    scope: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    urgency: Optional[Any] = None
    model_config = ConfigDict(extra='allow')

class ContextPayload(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]

class ContextResponse(BaseModel):
    accepted: bool
    reason: Optional[str] = None
    current_version: Optional[int] = None
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None

class Action(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: str
    trigger_id: str
    template_name: Optional[str] = None
    template_params: Optional[List[str]] = None
    body: str
    cta: str
    suppression_key: str
    rationale: str

class TickRequest(BaseModel):
    now: str
    available_triggers: List[str]

class TickResponse(BaseModel):
    actions: List[Action]

class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str
    from_role: str
    message: str
    turn_number: int
    received_at: Optional[str] = None

class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[str] = None
    wait_seconds: Optional[int] = None
    rationale: str
