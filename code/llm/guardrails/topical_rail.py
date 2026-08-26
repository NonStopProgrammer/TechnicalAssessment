"""LLM-4.5: topical/scope rail — off-topic requests get a fixed decline
without ever reaching the LLM (cost control + reduces prompt-injection
surface, SEC-3.5).

MVP default is a keyword-overlap heuristic — deliberately simple, and
noticeably less robust than the production adapter (NeMo Guardrails'
semantic intent classification, TOPICAL_RAIL_PROVIDER=nemo): a legitimate
question phrased without any of these keywords could be false-flagged, and
an off-topic question that happens to mention "risk" could slip through.
Acceptable for an MVP demonstrating the control point exists; not a
substitute for the real classifier before production traffic.
"""

import re
from abc import ABC, abstractmethod
from functools import lru_cache

from shared.config import get_settings

FIXED_DECLINE_MESSAGE = (
    "This assistant answers questions about financial regulatory compliance "
    "(Basel III, MiFID II, RBI directions) only. Please rephrase your question "
    "within that scope."
)

_COMPLIANCE_KEYWORDS = {
    "regulation", "regulatory", "compliance", "comply", "basel", "mifid", "rbi",
    "kyc", "aml", "sanction", "transaction", "risk", "capital", "audit", "circular",
    "directive", "exposure", "lending", "loan", "investment", "jurisdiction",
    "license", "penalty", "reporting", "tier", "counterparty", "derivative",
    "priority", "sector", "appropriateness", "customer", "diligence", "nbfc",
    "bank", "financial", "instrument", "threshold", "assessment", "policy",
}
_TOKEN_PATTERN = re.compile(r"[a-z]+")


class TopicalRail(ABC):
    @abstractmethod
    def is_in_scope(self, query: str) -> bool: ...


class KeywordTopicalRail(TopicalRail):
    def is_in_scope(self, query: str) -> bool:
        tokens = set(_TOKEN_PATTERN.findall(query.lower()))
        return bool(tokens & _COMPLIANCE_KEYWORDS)


class NeMoGuardrailsRail(TopicalRail):
    """Production adapter (LLM-4.5). Requires `nemoguardrails`
    (requirements-full.txt) and a configured rails directory.
    """

    def __init__(self, config_path: str = "./llm/guardrails/nemo_config"):
        from nemoguardrails import LLMRails, RailsConfig

        self._rails = LLMRails(RailsConfig.from_path(config_path))

    def is_in_scope(self, query: str) -> bool:
        response = self._rails.generate(messages=[{"role": "user", "content": query}])
        return "off_topic" not in (response.get("content", "") if isinstance(response, dict) else str(response))


@lru_cache
def get_topical_rail() -> TopicalRail:
    settings = get_settings()
    if settings.topical_rail_provider == "nemo":
        return NeMoGuardrailsRail()
    return KeywordTopicalRail()
