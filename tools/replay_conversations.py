import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vera.core.store import ContextStore
from vera.core.engine import DeterministicEngine
from vera.core.models import ContextPayload, Scope, ReplyRequest, TickRequest

def main():
    store = ContextStore()
    engine = DeterministicEngine(store)

    # Load basic context
    store.push(ContextPayload(
        scope=Scope.TRIGGER,
        context_id="trg_001",
        version=1,
        payload={"id": "trg_001", "kind": "perf_dip", "scope": "merchant", "merchant_id": "m_001"}
    ))
    store.push(ContextPayload(
        scope=Scope.MERCHANT,
        context_id="m_001",
        version=1,
        payload={"merchant_id": "m_001", "name": "Test Merchant", "subscription": {"status": "active"}}
    ))

    # Start outreach (tick)
    req = TickRequest(now="2026-04-26T10:00:00Z", available_triggers=["trg_001"])
    response = engine.tick(req)

    scenarios = [
        {"turn": 1, "message": "how does this work?"},
        {"turn": 2, "message": "I am out of office"},
        {"turn": 3, "message": "I am out of office"},
        {"turn": 4, "message": "yes proceed"}
    ]

    for s in scenarios:
        turn = s["turn"]
        msg = s["message"]

        prev_state = store.get(Scope.CONVERSATION, "conv_m_001_trg_001")
        prev_status = prev_state.payload.get("status") if prev_state else "NEW"

        reply_req = ReplyRequest(
            conversation_id="conv_m_001_trg_001",
            merchant_id="m_001",
            from_role="merchant",
            message=msg,
            turn_number=turn
        )

        res = engine.reply(reply_req)

        new_state = store.get(Scope.CONVERSATION, "conv_m_001_trg_001")

        print(f"--- Turn {turn} ---")
        print(f"input: {msg}")
        print(f"detected_intent: {new_state.payload.get('last_intent')}")
        print(f"previous_state: {prev_status}")
        print(f"new_state: {new_state.payload.get('status')}")
        print(f"decision: {res.action}")
        print(f"action: {res.body or res.action}")
        print(f"reason: {res.rationale}")

if __name__ == "__main__":
    main()
