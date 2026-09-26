import pytest
from pydantic import ValidationError
from vera.core.models import ContextPayload, Action, TickResponse, ReplyResponse

def test_action_validation():
    # Missing required fields
    with pytest.raises(ValidationError):
        Action(
            merchant_id="m_001",
            body="Hello"
        )
        
    # Valid action
    action = Action(
        conversation_id="conv_1",
        merchant_id="m_001",
        send_as="vera",
        trigger_id="trg_1",
        body="Hello",
        cta="none",
        suppression_key="key",
        rationale="Because"
    )
    assert action.conversation_id == "conv_1"
    
def test_reply_response_validation():
    with pytest.raises(ValidationError):
        ReplyResponse(action="invalid_action", rationale="Test")
        
    reply = ReplyResponse(action="wait", wait_seconds=86400, rationale="Test")
    assert reply.action == "wait"
    
def test_tick_response_validation():
    tick = TickResponse(actions=[])
    assert len(tick.actions) == 0
