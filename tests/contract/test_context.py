import pytest
from vera.core.models import ContextPayload
from vera.core.store import ContextStore

@pytest.fixture
def store():
    return ContextStore()

def test_context_identity_and_first_version(store):
    payload = ContextPayload(
        scope="merchant",
        context_id="m_001",
        version=1,
        payload={"name": "Test Merchant"}
    )
    
    response = store.push(payload)
    assert response.accepted is True
    assert response.ack_id == "ack_m_001_v1"
    assert response.stored_at is not None
    
    retrieved = store.get("merchant", "m_001")
    assert retrieved is not None
    assert retrieved.version == 1

def test_same_version_rejected(store):
    payload1 = ContextPayload(
        scope="merchant",
        context_id="m_001",
        version=1,
        payload={"name": "Test"}
    )
    store.push(payload1)
    
    payload2 = ContextPayload(
        scope="merchant",
        context_id="m_001",
        version=1,
        payload={"name": "Test Updated"}
    )
    response = store.push(payload2)
    
    assert response.accepted is False
    assert response.reason == "stale_version"
    assert response.current_version == 1

def test_older_version_rejected(store):
    payload1 = ContextPayload(
        scope="merchant",
        context_id="m_001",
        version=2,
        payload={"name": "Test"}
    )
    store.push(payload1)
    
    payload2 = ContextPayload(
        scope="merchant",
        context_id="m_001",
        version=1,
        payload={"name": "Test Updated"}
    )
    response = store.push(payload2)
    
    assert response.accepted is False
    assert response.reason == "stale_version"
    assert response.current_version == 2

def test_newer_version_accepted_and_replaces(store):
    payload1 = ContextPayload(
        scope="merchant",
        context_id="m_001",
        version=1,
        payload={"name": "Test"}
    )
    store.push(payload1)
    
    payload2 = ContextPayload(
        scope="merchant",
        context_id="m_001",
        version=2,
        payload={"name": "Test Updated"}
    )
    response = store.push(payload2)
    
    assert response.accepted is True
    assert response.ack_id == "ack_m_001_v2"
    
    retrieved = store.get("merchant", "m_001")
    assert retrieved is not None
    assert retrieved.version == 2
    assert retrieved.payload["name"] == "Test Updated"

def test_different_scope_same_id(store):
    payload1 = ContextPayload(
        scope="merchant",
        context_id="001",
        version=1,
        payload={}
    )
    store.push(payload1)
    
    payload2 = ContextPayload(
        scope="customer",
        context_id="001",
        version=1,
        payload={}
    )
    response = store.push(payload2)
    
    assert response.accepted is True
    
    assert store.get("merchant", "001") is not None
    assert store.get("customer", "001") is not None
