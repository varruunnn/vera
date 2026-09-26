import os
import json
import logging
from pydantic import BaseModel, Field
from typing import Optional
from vera.config.env import config
from vera.core.decision import Decision, MessageStrategy
from vera.core.evidence import DecisionEvidenceSet

logger = logging.getLogger(__name__)

class ComposerOutput(BaseModel):
    body: str = Field(description="The body text of the message")
    cta_text: str = Field(description="The call to action text, or 'none' if empty")

class GeminiComposer:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            # Lazy initialize
            api_key = config.gemini_api_key
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not configured")

            from google import genai
            self._client = genai.Client(api_key=api_key)
        return self._client

    def compose(self, decision: Decision) -> Optional[ComposerOutput]:
        if not decision.should_act or not decision.strategy:
            return None

        # Build prompt
        prompt = self._build_prompt(decision.evidence, decision.strategy)

        try:
            from google import genai
            # Use JSON schema for structured output
            response = self.client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ComposerOutput,
                    temperature=0.2,
                ),
            )
            data = json.loads(response.text)
            return ComposerOutput(**data)
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return None

    def _build_prompt(self, evidence: DecisionEvidenceSet, strategy: MessageStrategy) -> str:
        # Format evidence hierarchically
        domains = {}
        for e in evidence.items:
            domains.setdefault(e.source_domain, []).append(e)

        evidence_lines = []
        for domain, items in domains.items():
            evidence_lines.append(f"## {domain.capitalize()} Context")
            for e in items:
                evidence_lines.append(f"- {e.field_path}: {e.value}")
            evidence_lines.append("")

        evidence_text = "\n".join(evidence_lines)

        return f"""You are a controlled language composer. Write a message based ONLY on the evidence provided.

## Strategy
Audience: {strategy.audience}
Purpose: {strategy.purpose}
Tone: {strategy.tone}
Key Points: {', '.join(strategy.key_points)}

## Constraints
- Do NOT invent facts, numbers, dates, or offers.
- Do NOT add URLs.
- Do NOT make unsupported claims.
- If a fact is not in the Evidence, you cannot use it.

## Evidence
{evidence_text}

Produce a JSON response containing 'body' and 'cta_text'.
"""
