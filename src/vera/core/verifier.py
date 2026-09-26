import re
from dataclasses import dataclass
from vera.core.composer import ComposerOutput
from vera.core.evidence import DecisionEvidenceSet

@dataclass
class VerificationResult:
    is_valid: bool
    failures: list[str]

class OutputVerifier:
    def verify(self, output: ComposerOutput, evidence: DecisionEvidenceSet) -> VerificationResult:
        failures = []

        body = output.body.lower()

        # 1. No URLs
        if "http://" in body or "https://" in body or "www." in body:
            failures.append("URL detected in body")

        # 2. Check numeric claims (simple check: any 3+ digit number must appear in evidence)
        # We only check numbers >= 100 to avoid false positives on '1' or '2'
        numbers = re.findall(r'\b\d{3,}\b', output.body)
        if numbers:
            evidence_str = " ".join(str(e.value) for e in evidence.items).lower()
            for num in numbers:
                if num not in evidence_str:
                    failures.append(f"Invented number detected: {num}")

        # 3. Basic Date checking (e.g., YYYY-MM-DD or Month DD formats roughly)
        # We'll just look for year "2026" or "2027" for now
        years = re.findall(r'\b(2026|2027)\b', output.body)
        if years:
            evidence_str = " ".join(str(e.value) for e in evidence.items).lower()
            for year in years:
                if year not in evidence_str:
                    failures.append(f"Invented year detected: {year}")

        # 4. Check for empty
        if not output.body.strip():
            failures.append("Empty body")

        return VerificationResult(is_valid=len(failures) == 0, failures=failures)
