from app.pipeline.recommendations import build_recommendations
from app.pipeline.rules.base import CheckResult


def _check(id_, dimension, score, severity, recommendation=None) -> CheckResult:
    return CheckResult(
        id=id_,
        dimension=dimension,
        score=score,
        severity=severity,
        evidence=f"evidence for {id_}",
        recommendation=recommendation,
    )


def test_passed_checks_produce_no_recommendation():
    checks = [_check("a", "trust", 1.0, "info", None)]
    assert build_recommendations(checks) == []


def test_failed_checks_sorted_critical_first():
    checks = [
        _check("low_issue", "metadata", 0.5, "low", "fix low"),
        _check("critical_issue", "trust", 0.0, "critical", "fix critical"),
        _check("medium_issue", "accessibility", 0.3, "medium", "fix medium"),
        _check("passed", "structure", 1.0, "info", None),
    ]
    items = build_recommendations(checks)
    assert [i.check_id for i in items] == ["critical_issue", "medium_issue", "low_issue"]


def test_recommendation_item_shape():
    checks = [_check("image_alt_text", "accessibility", 0.2, "medium", "add alt text")]
    items = build_recommendations(checks)
    assert len(items) == 1
    item = items[0]
    assert item.issue == "Image Alt Text"
    assert item.impact == "evidence for image_alt_text"
    assert item.recommendation == "add alt text"
    assert item.to_dict()["dimension"] == "accessibility"
