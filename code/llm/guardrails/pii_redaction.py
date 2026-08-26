"""LLM-4.3: PII redaction before anything reaches a cache, log, or report
export (SEC-3.3 applies this on the outbound side even for internal
storage, not just external calls).

MVP default is a regex-based redactor covering the PII shapes most likely
in a transaction payload or free-text query (emails, phone numbers, card-
like numbers, India PAN/Aadhaar formats, generic long account numbers).
`requirements-full.txt`'s `presidio-analyzer`/`presidio-anonymizer` is the
production adapter — swap PII_REDACTION_PROVIDER=presidio once spaCy's
language model is available; the interface below does not change.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache

from shared.config import get_settings

_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "PHONE": re.compile(r"\+?\d[\d\-\s]{8,14}\d"),
    "PAN_IN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),  # India PAN
    "AADHAAR_IN": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),  # India Aadhaar (12 digits)
    "CARD_NUMBER": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ACCOUNT_NUMBER": re.compile(r"\b\d{9,18}\b"),
}
# Order matters: more specific patterns (PAN, Aadhaar, card) are checked
# before the generic long-digit-run account-number catch-all so that a PAN
# or card number isn't double-labelled as a generic account number.
_PATTERN_ORDER = ["EMAIL", "PHONE", "PAN_IN", "AADHAAR_IN", "CARD_NUMBER", "ACCOUNT_NUMBER"]


@dataclass
class PiiMatch:
    category: str
    original: str
    start: int
    end: int


@dataclass
class RedactionResult:
    redacted_text: str
    findings: list[PiiMatch] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return bool(self.findings)


class PiiRedactor(ABC):
    @abstractmethod
    def redact(self, text: str) -> RedactionResult: ...

    def redact_dict(self, data: dict) -> dict:
        """Recursively redacts every string value — used before logging a
        transaction payload or query (SEC-2.3 "input (PII-redacted)").
        """
        result = {}
        for key, value in data.items():
            result[key] = self._redact_value(value)
        return result

    def _redact_value(self, value):
        if isinstance(value, str):
            return self.redact(value).redacted_text
        if isinstance(value, dict):
            return self.redact_dict(value)
        if isinstance(value, list):
            # Recurse into list items too — a list of dicts (e.g. citations,
            # rule triggers) is exactly what FR-2/FR-4 payloads nest, and
            # skipping it here would silently leave any string PII inside
            # those items unredacted.
            return [self._redact_value(item) for item in value]
        return value


class RegexPiiRedactor(PiiRedactor):
    def redact(self, text: str) -> RedactionResult:
        findings: list[PiiMatch] = []
        redacted = text
        claimed: list[tuple[int, int]] = []

        for category in _PATTERN_ORDER:
            for match in _PATTERNS[category].finditer(text):
                span = match.span()
                if any(span[0] < end and start < span[1] for start, end in claimed):
                    continue  # already redacted by a more specific pattern
                claimed.append(span)
                findings.append(PiiMatch(category=category, original=match.group(), start=span[0], end=span[1]))

        for finding in sorted(findings, key=lambda f: f.start, reverse=True):
            placeholder = f"[REDACTED:{finding.category}]"
            redacted = redacted[: finding.start] + placeholder + redacted[finding.end :]

        return RedactionResult(redacted_text=redacted, findings=findings)


class PresidioRedactor(PiiRedactor):
    """Production adapter (LLM-4.3). Requires `presidio-analyzer` +
    `presidio-anonymizer` + a spaCy language model (requirements-full.txt).
    """

    def __init__(self):
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()

    def redact(self, text: str) -> RedactionResult:
        results = self._analyzer.analyze(text=text, language="en")
        anonymized = self._anonymizer.anonymize(text=text, analyzer_results=results)
        findings = [
            PiiMatch(category=r.entity_type, original=text[r.start : r.end], start=r.start, end=r.end)
            for r in results
        ]
        return RedactionResult(redacted_text=anonymized.text, findings=findings)


@lru_cache
def get_pii_redactor() -> PiiRedactor:
    settings = get_settings()
    if settings.pii_redaction_provider == "presidio":
        return PresidioRedactor()
    return RegexPiiRedactor()
