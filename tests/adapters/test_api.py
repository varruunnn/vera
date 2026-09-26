import pytest
from fastapi.testclient import TestClient
from vera.adapters.fastapi_app import app, store

client = TestClient(app)

def test_healthz():
    response = client.get("/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_metadata():
    response = client.get("/v1/metadata")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data

def test_context_and_tick():
    store.clear()
    
    # Push context
    resp = client.post("/v1/context", json={
        "scope": "trigger",
        "context_id": "trg_999",
        "version": 1,
        "payload": {"id": "trg_999", "kind": "perf_dip", "scope": "merchant", "merchant_id": "m_999"}
    })
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True
    
    client.post("/v1/context", json={
        "scope": "merchant",
        "context_id": "m_999",
        "version": 1,
        "payload": {"merchant_id": "m_999", "name": "API Merchant", "subscription": {"status": "active"}}
    })
    
    # Tick
    tick_resp = client.post("/v1/tick", json={
        "now": "2026-04-26T10:00:00Z",
        "available_triggers": ["trg_999"]
    })
    assert tick_resp.status_code == 200
    data = tick_resp.json()
    assert len(data["actions"]) == 1
    action = data["actions"][0]
    assert action["merchant_id"] == "m_999"

def test_reply_endpoint():
    # Rely on existing context from previous test (m_999, trg_999)
    resp = client.post("/v1/reply", json={
        "conversation_id": "conv_m_999_trg_999",
        "merchant_id": "m_999",
        "from_role": "merchant",
        "message": "yes proceed",
        "turn_number": 1
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    assert "execute" in data["rationale"].lower()
