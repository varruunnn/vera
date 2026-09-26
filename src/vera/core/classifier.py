import re
from typing import Optional
from vera.core.models import Intent

class IntentClassifier:
    def classify(self, text: str) -> Intent:
        text = text.lower().strip()

        # Auto-reply patterns (mocking common auto-replies)
        if "out of office" in text or "automated message" in text or "will reply as soon as possible" in text:
            return Intent.AUTO_REPLY

        # Opt-out
        if re.search(r'\b(stop|unsubscribe|cancel|opt out|remove me|do not contact)\b', text):
            return Intent.OPT_OUT

        # Positive Intent / Action Request
        if re.search(r'\b(yes|yeah|sure|okay let\'s do it|go ahead|proceed|sounds good|do it|approve)\b', text):
            # Check if it's asking to do something vs just positive
            if re.search(r'\b(do|send|book|schedule)\b', text) and "can you" in text:
                return Intent.ACTION_REQUEST
            return Intent.POSITIVE_INTENT

        # Negative
        if re.search(r'\b(no|nope|not interested|never|bad idea)\b', text):
            return Intent.NEGATIVE_INTENT

        # Question
        if "?" in text or re.search(r'\b(what|how|why|when|where|who)\b', text):
            return Intent.QUESTION

        # Uncertainty
        if re.search(r'\b(maybe|not sure|think about it|perhaps)\b', text):
            return Intent.UNCERTAINTY

        return Intent.OTHER
