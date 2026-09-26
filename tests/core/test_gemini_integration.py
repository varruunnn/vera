import pytest
from unittest.mock import patch, MagicMock
from vera.core.models import Action
from vera.core.engine import DeterministicEngine
from vera.core.decision import Decision, ActionIntent, MessageStrategy
from vera.core.evidence import DecisionEvidenceSet, Evidence
from vera.core.composer import ComposerOutput, GeminiComposer
from vera.core.verifier import OutputVerifier

@pytest.fixture
def mock_decision():
    evidence = DecisionEvidenceSet()
    evidence.add(Evidence("RAW_FACT", "Dr Meera", "merchant", "m_001", "identity.name", "Name"))
    evidence.add(Evidence("RAW_FACT", "Priya", "customer", "c_001", "identity.name", "Name"))

    intent = ActionIntent("customer", "notify", "m_001", "trg_1", "c_001", "supp_1")
    strategy = MessageStrategy("customer", "Alert", "professional", [], [], [], "none")

    return Decision(True, "Reason", evidence, intent, strategy)

def test_composer_disabled_by_default(mock_decision):
    engine = DeterministicEngine(MagicMock())
    action = engine._generate_action(mock_decision, use_gemini=False)

    assert action is not None
    assert "Priya" in action.body
    assert action.send_as == "merchant_on_behalf"
    assert action.merchant_id == "m_001"
    assert action.customer_id == "c_001"
    assert action.trigger_id == "trg_1"
    assert action.conversation_id == "conv_c_001_trg_1"

@patch('vera.core.composer.GeminiComposer.compose')
def test_gemini_unavailable_fallback(mock_compose, mock_decision):
    # Mock composer to return None (failure/timeout)
    mock_compose.return_value = None

    engine = DeterministicEngine(MagicMock())
    v_fails = []
    action = engine._generate_action(mock_decision, use_gemini=True, use_verifier=True, verifier_failures=v_fails)

    assert action is not None
    # Must fallback to deterministic deterministic output
    assert "Priya" in action.body
    assert "Composer failed or timed out" in v_fails

@patch('vera.core.composer.GeminiComposer.compose')
def test_gemini_malformed_output_verifier_fallback(mock_compose, mock_decision):
    # Mock composer to return something with a URL and invented number
    mock_compose.return_value = ComposerOutput(
        body="Check this out http://example.com and save 500 dollars!",
        cta_text="Click here"
    )

    engine = DeterministicEngine(MagicMock())
    v_fails = []
    action = engine._generate_action(mock_decision, use_gemini=True, use_verifier=True, verifier_failures=v_fails)

    assert action is not None
    # Must fallback because of verifier failure
    assert "http" not in action.body.lower()
    assert action.body == "Hello Priya, Dr Meera has a message for you."
    assert "URL detected in body" in v_fails
    assert "Invented number detected: 500" in v_fails

def test_verifier_rules(mock_decision):
    verifier = OutputVerifier()

    # 1. URL Rejection
    out_url = ComposerOutput(body="Visit www.google.com", cta_text="none")
    res = verifier.verify(out_url, mock_decision.evidence)
    assert not res.is_valid
    assert any("URL" in f for f in res.failures)

    # 2. Number rejection (500 not in evidence)
    out_num = ComposerOutput(body="You have 500 points", cta_text="none")
    res = verifier.verify(out_num, mock_decision.evidence)
    assert not res.is_valid
    assert any("Invented number" in f for f in res.failures)

    # 3. Valid output
    # Let's add 2026 to evidence
    mock_decision.evidence.add(Evidence("RAW_FACT", "2026", "trigger", "trg_1", "year", "Year"))
    out_valid = ComposerOutput(body="Hello Priya, this is 2026.", cta_text="none")
    res = verifier.verify(out_valid, mock_decision.evidence)
    assert res.is_valid

def test_metadata_ownership(mock_decision):
    # Ensure composer output is wrapped in deterministic metadata
    engine = DeterministicEngine(MagicMock())

    with patch('vera.core.composer.GeminiComposer.compose') as mock_compose:
        mock_compose.return_value = ComposerOutput(body="Valid body.", cta_text="none")
        action = engine._generate_action(mock_decision, use_gemini=True, use_verifier=True)

        assert action.body == "Valid body."
        assert action.send_as == "merchant_on_behalf" # Preserved!
        assert action.conversation_id == "conv_c_001_trg_1"
        assert action.merchant_id == "m_001"
