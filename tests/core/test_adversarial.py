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


def test_opt_out_vs_expired_semantics(base_engine):
    engine, store = base_engine
    
    # 1. Explicit opt-out blocks execution and returns 'end'
    res_opt = reply(engine, 'stop', turn=1)
    assert res_opt.action == 'end'
    
    # 2. Expired trigger blocks execution but returns 'wait', NOT 'end'
    store.push(ContextPayload(
        scope=Scope.TRIGGER,
        context_id='trg_exp',
        version=1,
        payload={'id': 'trg_exp', 'kind': 'perf_dip', 'scope': 'merchant', 'merchant_id': 'm_1', 'expires_at': '2020-01-01T00:00:00Z'}
    ))
    res_exp = engine.reply(ReplyRequest(conversation_id='conv_m_1_trg_exp', merchant_id='m_1', from_role='merchant', message='yes proceed', turn_number=1))
    assert res_exp.action == 'wait'
    assert 'expired' in res_exp.rationale.lower()
    
    # 3. Merchant subscription expiry does not become customer opt-out
    store.push(ContextPayload(
        scope=Scope.TRIGGER,
        context_id='trg_2',
        version=1,
        payload={'id': 'trg_2', 'kind': 'perf_dip', 'scope': 'merchant', 'merchant_id': 'm_2'}
    ))
    store.push(ContextPayload(
        scope=Scope.MERCHANT,
        context_id='m_2',
        version=1,
        payload={'merchant_id': 'm_2', 'name': 'Exp Merchant', 'subscription': {'status': 'expired'}}
    ))
    res_mexp = engine.reply(ReplyRequest(conversation_id='conv_m_2_trg_2', merchant_id='m_2', from_role='merchant', message='yes proceed', turn_number=1))
    assert res_mexp.action == 'wait'
    assert 'expired' in res_mexp.rationale.lower()
    
    # 4. Customer relationship expiry/lapse (opt-in = false) blocks execution, but is not 'end'
    store.push(ContextPayload(
        scope=Scope.TRIGGER,
        context_id='trg_cust',
        version=1,
        payload={'id': 'trg_cust', 'kind': 'cust_dip', 'scope': 'customer', 'customer_id': 'c_1', 'merchant_id': 'm_1'}
    ))
    store.push(ContextPayload(
        scope=Scope.CUSTOMER,
        context_id='c_1',
        version=1,
        payload={'customer_id': 'c_1', 'merchant_id': 'm_1', 'name': 'No Optin Cust', 'preferences': {'reminder_opt_in': False}}
    ))
    res_cust = engine.reply(ReplyRequest(conversation_id='conv_c_1_trg_cust', merchant_id='m_1', from_role='customer', message='yes proceed', turn_number=1))
    assert res_cust.action == 'wait'
    assert 'opted in' in res_cust.rationale.lower()

def test_consecutive_similar_replies_threshold(base_engine):
    engine, store = base_engine
    
    # First occurrence of 'Hello'
    req1 = ReplyRequest(conversation_id='conv_m_1_trg_1', merchant_id='m_1', from_role='merchant', message='Hello', turn_number=1)
    res1 = engine.reply(req1)
    
    state1 = store.get(Scope.CONVERSATION, 'conv_m_1_trg_1')
    assert state1.payload['consecutive_similar_replies'] == 0
    assert state1.payload['last_intent'] == 'OTHER'
    
    # Second occurrence of 'Hello'
    req2 = ReplyRequest(conversation_id='conv_m_1_trg_1', merchant_id='m_1', from_role='merchant', message='Hello', turn_number=2)
    res2 = engine.reply(req2)
    
    state2 = store.get(Scope.CONVERSATION, 'conv_m_1_trg_1')
    assert state2.payload['consecutive_similar_replies'] == 1
    assert state2.payload['last_intent'] == 'AUTO_REPLY'
    assert res2.action == 'wait'
