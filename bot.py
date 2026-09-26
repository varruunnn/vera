from typing import Optional, Dict, Any, List
from vera.core.models import ContextPayload, Scope, TickRequest
from vera.core.store import ContextStore
from vera.core.engine import DeterministicEngine

def compose(category: Dict[str, Any], merchant: Dict[str, Any], trigger: Dict[str, Any], customer: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    store = ContextStore()
    engine = DeterministicEngine(store)

    # Load Contexts
    store.push(ContextPayload(scope=Scope.CATEGORY, context_id=category["category_id"], version=1, payload=category))
    store.push(ContextPayload(scope=Scope.MERCHANT, context_id=merchant["merchant_id"], version=1, payload=merchant))

    if customer:
        store.push(ContextPayload(scope=Scope.CUSTOMER, context_id=customer["customer_id"], version=1, payload=customer))

    trigger_id = trigger.get("id", trigger.get("trigger_id"))
    store.push(ContextPayload(scope=Scope.TRIGGER, context_id=trigger_id, version=1, payload=trigger))

    # Perform Tick
    request = TickRequest(
        now="2026-04-26T10:00:00Z",
        available_triggers=[trigger_id]
    )

    response = engine.tick(request)
    return [action.model_dump() for action in response.actions]
