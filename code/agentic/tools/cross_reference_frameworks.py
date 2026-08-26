"""AGENT-1.4: resolves overlaps/conflicts across frameworks instead of
concatenating retrieval hits naively — this is the tool that directly
answers the assignment's "cross-regulation complexity" pain point.

Two distinct behaviors, per AGENT-1.4 and AGENT-3.5:
  - Overlapping thresholds that merely differ in strictness are resolved
    automatically (the stricter one is surfaced).
  - A genuine contradiction (a floor from one framework that is
    numerically incompatible with a ceiling from another) is surfaced as
    an explicit conflict for human judgment, never silently resolved.
"""

import re
from dataclasses import dataclass, field

from shared.models.assessment import FrameworkConflict
from shared.models.chunk import RetrievedChunk

_NOT_EXCEED_PATTERN = re.compile(r"must not exceed\s+(\d+(?:\.\d+)?)\s?%", re.IGNORECASE)
_AT_LEAST_PATTERN = re.compile(r"(?:at least|maintain(?:\s+a)?)\s+(\d+(?:\.\d+)?)\s?%", re.IGNORECASE)


@dataclass
class CrossReferenceResolution:
    by_framework: dict[str, list[RetrievedChunk]] = field(default_factory=dict)
    conflicts: list[FrameworkConflict] = field(default_factory=list)
    stricter_thresholds: dict[str, float] = field(default_factory=dict)


def cross_reference_frameworks(retrieved_chunks: list[RetrievedChunk]) -> CrossReferenceResolution:
    resolution = CrossReferenceResolution()
    for retrieved in retrieved_chunks:
        resolution.by_framework.setdefault(retrieved.chunk.framework.value, []).append(retrieved)

    if len(resolution.by_framework) > 1:
        _resolve_overlapping_thresholds(resolution)
    return resolution


def _resolve_overlapping_thresholds(resolution: CrossReferenceResolution) -> None:
    ceilings: list[tuple[str, str, float]] = []  # (framework, clause_id, value)
    floors: list[tuple[str, str, float]] = []

    for framework, chunks in resolution.by_framework.items():
        for retrieved in chunks:
            for match in _NOT_EXCEED_PATTERN.finditer(retrieved.chunk.text):
                ceilings.append((framework, retrieved.chunk.clause_id, float(match.group(1))))
            for match in _AT_LEAST_PATTERN.finditer(retrieved.chunk.text):
                floors.append((framework, retrieved.chunk.clause_id, float(match.group(1))))

    if ceilings:
        # RAG/AGENT-1.4: of multiple applicable ceilings, the stricter
        # (lower) one governs.
        resolution.stricter_thresholds["lowest_ceiling_pct"] = min(value for _, _, value in ceilings)
    if floors:
        resolution.stricter_thresholds["highest_floor_pct"] = max(value for _, _, value in floors)

    for c_framework, c_clause, c_value in ceilings:
        for f_framework, f_clause, f_value in floors:
            if c_framework == f_framework:
                continue
            if f_value > c_value:
                # Mutually impossible to satisfy both (must be >= f_value
                # AND <= c_value with f_value > c_value) — AGENT-3.5: a
                # true conflict, surfaced rather than silently resolved.
                resolution.conflicts.append(
                    FrameworkConflict(
                        description=(
                            f"{f_framework} §{f_clause} requires at least {f_value}% while {c_framework} "
                            f"§{c_clause} caps it at {c_value}% — mutually inconsistent, requires human review."
                        ),
                        conflicting_rules=[f"{f_framework}:{f_clause}", f"{c_framework}:{c_clause}"],
                    )
                )
