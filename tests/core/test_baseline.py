from bot import compose
from vera.core.store import ContextStore
from vera.core.engine import DeterministicEngine
from vera.core.models import TriggerContext, TickRequest, Scope, ContextPayload

def test_compose_merchant_trigger():
    cat = {"category_id": "cat_1", "name": "Dental"}
    merchant = {"merchant_id": "m_001", "name": "Dr Meera"}
    trigger = {"id": "trg_1", "scope": "merchant", "kind": "performance_dip", "merchant_id": "m_001"}

    actions = compose(cat, merchant, trigger)
    assert len(actions) == 1
    action = actions[0]

    assert action["send_as"] == "vera"
    assert "audience" not in action # It's not in OutputAction
    assert "Dr Meera" in action["body"]
    assert action["merchant_id"] == "m_001"
    assert action["customer_id"] is None
    assert action["conversation_id"] == "conv_m_001_trg_1"

def test_compose_customer_trigger():
    cat = {"category_id": "cat_1", "name": "Dental"}
    merchant = {"merchant_id": "m_001", "name": "Dr Meera"}
    customer = {"customer_id": "c_001", "merchant_id": "m_001", "name": "Priya"}
    trigger = {"id": "trg_1", "scope": "customer", "kind": "recall_due", "merchant_id": "m_001", "customer_id": "c_001"}

    actions = compose(cat, merchant, trigger, customer)
    assert len(actions) == 1
    action = actions[0]

    assert action["send_as"] == "merchant_on_behalf"
    assert "Dr Meera" in action["body"]
    assert "Priya" in action["body"]
    assert action["customer_id"] == "c_001"
    assert action["conversation_id"] == "conv_c_001_trg_1"

def test_compose_insufficient_evidence():
    cat = {"category_id": "cat_1", "name": "Dental"}
    merchant = {"merchant_id": "m_001", "name": "Dr Meera"}
    # Trigger missing target_id and missing customer context
    trigger = {"id": "trg_1", "scope": "customer", "kind": "recall_due"}

    actions = compose(cat, merchant, trigger)
    assert len(actions) == 0

def test_compose_determinism():
    cat = {"category_id": "cat_1", "name": "Dental"}
    merchant = {"merchant_id": "m_001", "name": "Dr Meera"}
    trigger = {"id": "trg_1", "scope": "merchant", "kind": "performance_dip", "merchant_id": "m_001"}

    actions1 = compose(cat, merchant, trigger)
    actions2 = compose(cat, merchant, trigger)

    assert actions1 == actions2
