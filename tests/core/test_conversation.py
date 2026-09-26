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

def test_positive_intent_transition(base_engine):
    engine, store = base_engine

    req = ReplyRequest(
        conversation_id="conv_m_1_trg_1",
        merchant_id="m_1",
        from_role="merchant",
        message="yes I want to join",
        turn_number=1
    )

    response = engine.reply(req)
    assert response.action == "send"
    assert "Executing your request now" in response.body

    conv = store.get(Scope.CONVERSATION, "conv_m_1_trg_1")
    assert conv is not None
    state = ConversationState(**conv.payload)
    assert state.positive_intent is True

def test_opt_out_behavior(base_engine):
    engine, store = base_engine

    req = ReplyRequest(
        conversation_id="conv_m_1_trg_1",
        merchant_id="m_1",
        from_role="merchant",
        message="stop messaging me",
        turn_number=1
    )

    response = engine.reply(req)
    assert response.action == "end"

    conv = store.get(Scope.CONVERSATION, "conv_m_1_trg_1")
    state = ConversationState(**conv.payload)
    assert state.opt_out is True
    assert state.status == ConversationStatus.OPTED_OUT

def test_auto_reply_loop(base_engine):
    engine, store = base_engine

    req1 = ReplyRequest(
        conversation_id="conv_m_1_trg_1",
        merchant_id="m_1",
        from_role="merchant",
        message="I am out of office",
        turn_number=1
    )

    req2 = ReplyRequest(
        conversation_id="conv_m_1_trg_1",
        merchant_id="m_1",
        from_role="merchant",
        message="I am out of office",
        turn_number=2
    )

    engine.reply(req1)
    # First auto-reply might just engage or wait depending on baseline, but let's test second
    response = engine.reply(req2)
    assert response.action == "wait"
    assert "Auto-reply loop detected" in response.rationale

def test_question_uncertainty(base_engine):
    engine, store = base_engine

    req = ReplyRequest(
        conversation_id="conv_m_1_trg_1",
        merchant_id="m_1",
        from_role="merchant",
        message="how much does it cost?",
        turn_number=1
    )

    response = engine.reply(req)
    assert response.action == "wait"
    assert "question" in response.rationale.lower()

def test_negative_intent(base_engine):
    engine, store = base_engine

    req = ReplyRequest(
        conversation_id="conv_m_1_trg_1",
        merchant_id="m_1",
        from_role="merchant",
        message="no thanks",
        turn_number=1
    )

    response = engine.reply(req)
    assert response.action == "wait"
    assert "negative" in response.rationale.lower()
