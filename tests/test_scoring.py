import pytest

from app.pipeline.scoring import DIMENSION_WEIGHTS, score_profile


def _profile_with_scores(scores: dict[str, float]) -> dict:
    return {"dimensions": {dim: {"score": s, "checks": {}} for dim, s in scores.items()}}


def test_weights_sum_to_one():
    assert abs(sum(w.weight for w in DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9


def test_perfect_profile_scores_100():
    profile = _profile_with_scores({dim: 1.0 for dim in DIMENSION_WEIGHTS})
    result = score_profile(profile)
    assert result.overall_score == 100.0
    assert all(d.weighted_contribution == d.weight for d in result.dimensions)


def test_zero_profile_scores_0():
    profile = _profile_with_scores({dim: 0.0 for dim in DIMENSION_WEIGHTS})
    result = score_profile(profile)
    assert result.overall_score == 0.0


def test_weighted_contribution_matches_weight_times_score():
    profile = _profile_with_scores({dim: 0.5 for dim in DIMENSION_WEIGHTS})
    result = score_profile(profile)
    for d in result.dimensions:
        assert d.weighted_contribution == pytest.approx(d.weight * 0.5, abs=1e-6)
    assert result.overall_score == pytest.approx(50.0, abs=0.1)


def test_missing_dimension_raises():
    incomplete = _profile_with_scores({"trust": 1.0})
    with pytest.raises(ValueError, match="missing dimension"):
        score_profile(incomplete)
