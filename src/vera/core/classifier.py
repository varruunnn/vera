import re
from typing import Optional
from vera.core.models import Intent

class IntentClassifier:
    def classify(self, text: str) -> Intent:
        text = text.lower().strip()

        # Opt-out
        if re.search(r'\b(stop|unsubscribe|cancel|opt out|remove me|do not contact)\b', text):
            return Intent.OPT_OUT

        # Negative
        if re.search(r'\b(no|nope|not interested|never|bad idea)\b', text):
            return Intent.NEGATIVE_INTENT

        # Uncertainty
        if re.search(r'\b(maybe|not sure|think about it|perhaps|might)\b', text):
            return Intent.UNCERTAINTY

        # Question
        if "?" in text or re.search(r'\b(what|how|why|when|where|who)\b', text):
            return Intent.QUESTION

        # Positive Intent / Action Request
        if re.search(r'\b(yes|yeah|sure|okay let\'s do it|go ahead|proceed|sounds good|do it|approve)\b', text):
            # Check for conditions/constraints
            if re.search(r'\b(if|but|provided|only if|first tell me|can i)\b', text):
                return Intent.CONDITIONAL_POSITIVE_INTENT
                
            # Check if it's asking to do something vs just positive
            if re.search(r'\b(do|send|book|schedule)\b', text) and "can you" in text:
                return Intent.ACTION_REQUEST
            return Intent.POSITIVE_INTENT

        return Intent.OTHER
