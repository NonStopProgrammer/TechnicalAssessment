"""LLM-3.5 structured-output schemas.

Deliberately narrow: the LLM only ever produces prose (an answer, or a
narrative explaining numbers/rules computed elsewhere). Risk ratings,
citations, and required actions come from deterministic code
(agentic/tools/calculate_risk_rating.py, generate_citation_bundle.py) per
AGENT-1.5's "keeps the rating auditable and reproducible independent of LLM
sampling variance" — the LLM is never the source of truth for those fields,
only for explaining them, which is why these schemas are this small.
"""

from pydantic import BaseModel, Field


class QaAnswerOutput(BaseModel):
    answer: str
    citations_used: list[str] = Field(default_factory=list)


class NarrativeOutput(BaseModel):
    narrative: str
    key_points: list[str] = Field(default_factory=list)
