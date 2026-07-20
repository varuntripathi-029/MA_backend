"""Common input/output shape for every Rule Engine check.

Each check is an independent function: (CheckContext) -> CheckResult. This
lets checks be added, removed, and unit-tested in isolation instead of
living inside one monolithic scoring function.
"""

from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from app.pipeline.crawler import CrawlResult
from app.pipeline.extractor import ExtractedFeatures

Severity = Literal["info", "low", "medium", "high", "critical"]


@dataclass
class CheckContext:
    features: ExtractedFeatures
    crawl: CrawlResult


@dataclass
class CheckResult:
    id: str
    dimension: str
    score: float  # 0.0-1.0, this check's own normalized score
    severity: Severity  # "info" when score == 1.0 (nothing to flag)
    evidence: str  # the actual extracted value/snippet that justifies the score
    recommendation: str | None  # None when score == 1.0

    def to_dict(self) -> dict:
        return asdict(self)


class CheckFn(Protocol):
    def __call__(self, ctx: CheckContext) -> CheckResult: ...


def result(
    check_id: str,
    dimension: str,
    score: float,
    evidence: str,
    severity_if_imperfect: Severity,
    recommendation: str | None,
) -> CheckResult:
    """Helper: severity collapses to "info" and recommendation to None
    whenever a check fully passes (score == 1.0), so each check only has to
    state what severity a *failure* of that check carries."""
    passed = score >= 1.0
    return CheckResult(
        id=check_id,
        dimension=dimension,
        score=round(score, 4),
        severity="info" if passed else severity_if_imperfect,
        evidence=evidence,
        recommendation=None if passed else recommendation,
    )
