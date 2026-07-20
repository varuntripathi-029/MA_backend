"""Module 8: Recommendation Engine.

Deterministic aggregation of Module 4's existing per-check
recommendation/evidence/severity fields into sorted (critical first)
issue/impact/recommendation records. No new LLM call here — that would
violate aim.md principle #3 ("LLM used in exactly one place"). Module 6's
LLM-generated recommendations are complementary narrative color shown
alongside this list, not a replacement for it or a second source of truth.
"""

from dataclasses import asdict, dataclass

from app.pipeline.rules.base import CheckResult

# Only used to sort; "info" (a fully-passed check) never reaches this list
# since such checks carry no recommendation.
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _humanize(check_id: str) -> str:
    return check_id.replace("_", " ").title()


@dataclass
class RecommendationItem:
    check_id: str
    dimension: str
    severity: str
    issue: str  # human-readable label of what failed
    impact: str  # the concrete detected problem — the check's own evidence
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_recommendations(checks: list[CheckResult]) -> list[RecommendationItem]:
    """checks is Module 4's raw output. Only checks that didn't fully pass
    carry a recommendation (see rules/base.py's `result()` helper) — those
    are the only ones that produce a record here."""
    items = [
        RecommendationItem(
            check_id=c.id,
            dimension=c.dimension,
            severity=c.severity,
            issue=_humanize(c.id),
            impact=c.evidence,
            recommendation=c.recommendation,
        )
        for c in checks
        if c.recommendation is not None
    ]
    items.sort(key=lambda item: _SEVERITY_ORDER.get(item.severity, len(_SEVERITY_ORDER)))
    return items
