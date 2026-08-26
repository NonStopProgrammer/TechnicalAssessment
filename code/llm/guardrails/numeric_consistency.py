"""LLM-4.6: numeric-consistency guardrail for FR-4 report narratives — any
number the LLM states in prose must match a deterministically-computed
aggregate; a mismatch blocks report finalization rather than shipping a
report with a hallucinated statistic.

MVP limitation: this flags any number in the narrative that doesn't trace
back to an expected value, which can over-flag benign numbers unrelated to
the statistics (an ordinal, a year mentioned in passing). Prompt templates
(`llm/prompts/report_narrative.v1.jinja2`) are written to discourage the
model from introducing extra figures at all, which keeps false positives
rare in practice; a production system would allowlist common non-stat
numeric patterns (dates, section numbers) explicitly.
"""

import re
from dataclasses import dataclass, field

_NUMBER_PATTERN = re.compile(r"\d[\d,]*\.?\d*%?")


@dataclass
class NumericConsistencyResult:
    is_consistent: bool
    unexplained_numbers: list[str] = field(default_factory=list)


def _flatten_numeric_strings(value) -> set[str]:
    numbers: set[str] = set()
    if isinstance(value, dict):
        for v in value.values():
            numbers |= _flatten_numeric_strings(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            numbers |= _flatten_numeric_strings(v)
    elif isinstance(value, bool):
        pass
    elif isinstance(value, (int, float)):
        numbers.add(str(value))
        numbers.add(f"{value:,}")
    return numbers


def check_numeric_consistency(narrative: str, expected_stats: dict) -> NumericConsistencyResult:
    expected_numbers = _flatten_numeric_strings(expected_stats)
    mentioned = {m.rstrip("%").replace(",", "") for m in _NUMBER_PATTERN.findall(narrative)}
    expected_normalized = {n.rstrip("%").replace(",", "") for n in expected_numbers}

    unexplained = sorted(mentioned - expected_normalized)
    return NumericConsistencyResult(is_consistent=not unexplained, unexplained_numbers=unexplained)
