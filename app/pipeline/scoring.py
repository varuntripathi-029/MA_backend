"""Module 7: Scoring Engine.

Deterministic weighted rubric over the 6 dimensions the Rule Engine (Module
4) actually produces: structure, metadata, accessibility, structured_data,
trust, discoverability. Weights are hand-set below with a one-line rationale
each — no regression fitting (aim.md principle #2).

DIMENSION_WEIGHTS is the single source of truth for weights. Nothing else in
the codebase should hardcode a weight or rationale: GET /api/methodology
(app/api/methodology.py) reads this same dict, so the published methodology
page and the number the engine actually computes can never drift apart.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DimensionWeight:
    weight: float
    rationale: str


DIMENSION_WEIGHTS: dict[str, DimensionWeight] = {
    "trust": DimensionWeight(
        0.20,
        "A site an agent can't reliably fetch — bad HTTP status, invalid SSL — blocks every "
        "other capability, so trust failures are weighted heaviest.",
    ),
    "discoverability": DimensionWeight(
        0.20,
        "An agent that can't find pricing, docs, or a sitemap can't act on a site no matter how "
        "well-structured the content it does reach is.",
    ),
    "structure": DimensionWeight(
        0.15,
        "Semantic HTML and heading hierarchy are how an agent parses page layout without a "
        "rendered, human view of it.",
    ),
    "metadata": DimensionWeight(
        0.15,
        "Title, meta description, Open Graph, and canonical URL are the first machine-readable "
        "summary of what a page is, read before any content.",
    ),
    "accessibility": DimensionWeight(
        0.15,
        "ARIA landmarks and alt text are machine-readable semantics as much as they are human "
        "accessibility aids — the same signal serves both.",
    ),
    "structured_data": DimensionWeight(
        0.15,
        "JSON-LD/schema.org is the most explicit machine-readable format a page can offer, "
        "distinct from metadata's looser, less structured signals.",
    ),
}

_weight_sum = sum(w.weight for w in DIMENSION_WEIGHTS.values())
assert abs(_weight_sum - 1.0) < 1e-9, f"DIMENSION_WEIGHTS must sum to 1.0, got {_weight_sum}"


@dataclass
class DimensionScore:
    dimension: str
    score: float  # 0.0-1.0, as computed by Module 4/5 — copied through, not recomputed
    weight: float
    weighted_contribution: float  # score * weight, 0.0-weight


@dataclass
class ScoreResult:
    overall_score: float  # 0-100
    dimensions: list[DimensionScore]

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "dimensions": [
                {
                    "dimension": d.dimension,
                    "score": d.score,
                    "weight": d.weight,
                    "weighted_contribution": d.weighted_contribution,
                }
                for d in self.dimensions
            ],
        }


def score_profile(profile: dict) -> ScoreResult:
    """profile is a Module 5 MachineProfile.to_dict() (or equivalent dict).
    Reads each dimension's already-computed score; performs no rule
    evaluation of its own."""
    dimensions_data = profile.get("dimensions", {})
    missing = set(DIMENSION_WEIGHTS) - set(dimensions_data)
    if missing:
        raise ValueError(f"profile is missing dimension(s) required by the scoring rubric: {sorted(missing)}")

    dim_scores = []
    total = 0.0
    for dim, weight_info in DIMENSION_WEIGHTS.items():
        dim_score = dimensions_data[dim]["score"]
        contribution = dim_score * weight_info.weight
        total += contribution
        dim_scores.append(
            DimensionScore(
                dimension=dim,
                score=dim_score,
                weight=weight_info.weight,
                weighted_contribution=round(contribution, 4),
            )
        )

    return ScoreResult(overall_score=round(total * 100, 2), dimensions=dim_scores)
