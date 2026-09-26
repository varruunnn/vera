import pytest
from fastapi.testclient import TestClient
from vera.adapters.fastapi_app import app, store

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_store():
    store.clear()

def test_healthz():
    response = client.get("/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_metadata():
    response = client.get("/v1/metadata")
    assert response.status_code == 200
    assert "version" in response.json()

def test_context_push_first_version():
    payload = {
        "scope": "merchant",
        "context_id": "m_001",
        "version": 1,
        "payload": {"name": "Test"}
    }
    response = client.post("/v1/context", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] is True
    assert "ack_id" in data

def test_context_push_same_version_conflict():
    payload = {
        "scope": "merchant",
        "context_id": "m_001",
        "version": 1,
        "payload": {"name": "Test"}
    }
    client.post("/v1/context", json=payload)
    
    # Push same version again
    response = client.post("/v1/context", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["accepted"] is False
    assert data["reason"] == "stale_version"
    assert data["current_version"] == 1

def test_context_push_older_version_conflict():
    payload2 = {
        "scope": "merchant",
        "context_id": "m_001",
        "version": 2,
        "payload": {"name": "Test 2"}
    }
    client.post("/v1/context", json=payload2)
    
    payload1 = {
        "scope": "merchant",
        "context_id": "m_001",
        "version": 1,
        "payload": {"name": "Test 1"}
    }
    response = client.post("/v1/context", json=payload1)
    assert response.status_code == 409
    data = response.json()
    assert data["accepted"] is False
    assert data["reason"] == "stale_version"
    assert data["current_version"] == 2

def test_context_push_newer_version_replaces():
    payload1 = {
        "scope": "merchant",
        "context_id": "m_001",
        "version": 1,
        "payload": {"name": "Test 1"}
    }
    client.post("/v1/context", json=payload1)
    
    payload2 = {
        "scope": "merchant",
        "context_id": "m_001",
        "version": 2,
        "payload": {"name": "Test 2"}
    }
    response = client.post("/v1/context", json=payload2)
    assert response.status_code == 200
    assert response.json()["accepted"] is True

def test_tick_empty():
    response = client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": []})
    assert response.status_code == 200
    assert response.json() == {"actions": []}

def test_reply_stop():
    payload = {
        "conversation_id": "conv_1",
        "merchant_id": "m_001",
        "from_role": "merchant",
        "message": "stop",
        "turn_number": 1
    }
    response = client.post("/v1/reply", json=payload)
    assert response.status_code == 200
    assert response.json()["action"] == "end"
