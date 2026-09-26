import pytest
from vera.core.engine import DeterministicEngine
from vera.core.store import ContextStore
from vera.core.models import ContextPayload, Scope, ReplyRequest, ConversationStatus, ConversationState
from vera.core.classifier import IntentClassifier

@pytest.fixture
def base_engine():
    store = ContextStore()
    store.push(ContextPayload(
        scope=Scope.TRIGGER,
        context_id="trg_1",
        version=1,
        payload={"id": "trg_1", "kind": "perf_dip", "scope": "merchant", "merchant_id": "m_1"}
    ))
    store.push(ContextPayload(
        scope=Scope.MERCHANT,
        context_id="m_1",
        version=1,
        payload={"merchant_id": "m_1", "name": "Test Merchant", "subscription": {"status": "active"}}
    ))
    return DeterministicEngine(store), store

def reply(engine, msg, turn=1):
    return engine.reply(ReplyRequest(
        conversation_id="conv_m_1_trg_1",
        merchant_id="m_1",
        from_role="merchant",
        message=msg,
        turn_number=turn
    ))

def test_adversarial_positive(base_engine):
    engine, _ = base_engine
    for msg in ["yes", "yes proceed", "okay let's do it"]:
        assert reply(engine, msg).action == "send"

def test_adversarial_conditional(base_engine):
    engine, _ = base_engine
    for msg in [
        "yes, but only if it's free",
        "yes if Tuesday works",
        "go ahead but first tell me the price",
        "yes, provided I can choose the time"
    ]:
        assert reply(engine, msg).action == "wait"

def test_adversarial_questions(base_engine):
    engine, _ = base_engine
    for msg in [
        "yes, but what does it cost?",
        "can I join?",
        "how does this work?"
    ]:
        assert reply(engine, msg).action == "wait"

def test_adversarial_uncertainty(base_engine):
    engine, _ = base_engine
    for msg in ["maybe", "I'm not sure", "I might be interested"]:
        assert reply(engine, msg).action == "wait"

def test_adversarial_negative(base_engine):
    engine, _ = base_engine
    for msg in ["no", "not interested"]:
        assert reply(engine, msg).action == "wait"

def test_adversarial_optout(base_engine):
    engine, _ = base_engine
    for msg in ["stop", "unsubscribe", "don't contact me again"]:
        assert reply(engine, msg).action == "end"

def test_adversarial_repeated(base_engine):
    engine, _ = base_engine
    # one "I am out of office" - Should NOT be AUTO_REPLY immediately unless exact match
    res1 = reply(engine, "I am out of office", turn=1)
    # The baseline will just wait on OTHER intent because it's already engaged, wait, it's not engaged yet!
    # Let's check status!
    
    # 2. repeated identical
    res2 = reply(engine, "I am out of office", turn=2)
    assert res2.action == "wait"
    assert "loop detected" in res2.rationale.lower()
    
    # 4. two similar but not identical
    store2 = ContextStore()
    store2.push(ContextPayload(scope=Scope.TRIGGER, context_id='trg_1', version=1, payload={'id': 'trg_1', 'kind': 'perf_dip', 'scope': 'merchant', 'merchant_id': 'm_1'}))
    store2.push(ContextPayload(scope=Scope.MERCHANT, context_id='m_1', version=1, payload={'merchant_id': 'm_1', 'name': 'Test Merchant', 'subscription': {'status': 'active'}}))
    engine = DeterministicEngine(store2)
    res1 = reply(engine, "I am out of office today", turn=1)
    res2 = reply(engine, "I am out of office tomorrow", turn=2)
    assert "loop detected" not in res2.rationale.lower()

    # 5. normal human reply containing automated words
    store3 = ContextStore()
    store3.push(ContextPayload(scope=Scope.TRIGGER, context_id='trg_1', version=1, payload={'id': 'trg_1', 'kind': 'perf_dip', 'scope': 'merchant', 'merchant_id': 'm_1'}))
    store3.push(ContextPayload(scope=Scope.MERCHANT, context_id='m_1', version=1, payload={'merchant_id': 'm_1', 'name': 'Test Merchant', 'subscription': {'status': 'active'}}))
    engine = DeterministicEngine(store3)
    res1 = reply(engine, "this is an automated message I hate it", turn=1)
    assert "loop detected" not in res1.rationale.lower()

