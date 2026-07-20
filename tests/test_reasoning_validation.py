"""Unit tests for Module 6's citation/polarity validators — the eval for
"does the model reliably cite real fields" (plan.md). No network/Groq calls:
these test _validate_citations directly against a hand-built profile +
ReasoningReport, not generate_report()."""

from app.pipeline.reasoning import GroundedClaim, ReasoningReport, _validate_citations

PROFILE = {
    "site": {"sitemap_found": True, "https": True, "robots_allowed": False},
    "content": {"json_ld_types": [], "title": "Acme"},
    "dimensions": {
        "accessibility": {
            "score": 1.0,
            "checks": {
                "aria_landmarks": {
                    "id": "aria_landmarks",
                    "dimension": "accessibility",
                    "score": 1.0,
                    "severity": "info",
                    "evidence": "56 elements carry an ARIA role/attribute",
                    "recommendation": None,
                }
            },
        },
        "trust": {
            "score": 0.0,
            "checks": {
                "http_status": {
                    "id": "http_status",
                    "dimension": "trust",
                    "score": 0.0,
                    "severity": "critical",
                    "evidence": "HTTP 500",
                    "recommendation": "Return HTTP 200",
                }
            },
        },
    },
}


def _report(**section_overrides) -> ReasoningReport:
    base = {
        "purpose": "test",
        "target_users": [],
        "agent_strengths": [],
        "agent_weaknesses": [],
        "missing_information": [],
        "confidence": 0.5,
        "recommendations": [],
    }
    base.update(section_overrides)
    return ReasoningReport.model_validate(base)


def test_unresolved_path_is_flagged():
    report = _report(agent_weaknesses=[GroundedClaim(text="x", citation="dimensions.nonexistent.score")])
    issues = _validate_citations(report, PROFILE)
    assert len(issues) == 1
    assert issues[0].issue_type == "unresolved_path"


def test_valid_weakness_citation_no_issue():
    report = _report(agent_weaknesses=[GroundedClaim(text="HTTP errors", citation="dimensions.trust.checks.http_status")])
    assert _validate_citations(report, PROFILE) == []


def test_weakness_citing_a_passing_check_is_polarity_mismatch():
    report = _report(
        agent_weaknesses=[GroundedClaim(text="missing ARIA", citation="dimensions.accessibility.checks.aria_landmarks")]
    )
    issues = _validate_citations(report, PROFILE)
    assert len(issues) == 1
    assert issues[0].issue_type == "polarity_mismatch"


def test_strength_citing_a_failing_check_is_polarity_mismatch():
    report = _report(
        agent_strengths=[GroundedClaim(text="great http status", citation="dimensions.trust.checks.http_status")]
    )
    issues = _validate_citations(report, PROFILE)
    assert len(issues) == 1
    assert issues[0].issue_type == "polarity_mismatch"


def test_strength_citing_a_passing_check_no_issue():
    report = _report(
        agent_strengths=[GroundedClaim(text="good ARIA coverage", citation="dimensions.accessibility.checks.aria_landmarks")]
    )
    assert _validate_citations(report, PROFILE) == []


def test_boolean_field_polarity():
    # site.robots_allowed is False -> a weakness citing it correctly is fine
    ok = _report(agent_weaknesses=[GroundedClaim(text="robots disallow", citation="site.robots_allowed")])
    assert _validate_citations(ok, PROFILE) == []

    # site.sitemap_found is True -> claiming it as a weakness is a mismatch
    bad = _report(agent_weaknesses=[GroundedClaim(text="no sitemap", citation="site.sitemap_found")])
    issues = _validate_citations(bad, PROFILE)
    assert len(issues) == 1
    assert issues[0].issue_type == "polarity_mismatch"


def test_empty_list_field_counts_as_negative():
    # content.json_ld_types is [] -> a missing_information claim about it is correctly negative
    report = _report(
        missing_information=[GroundedClaim(text="no structured data", citation="content.json_ld_types")]
    )
    assert _validate_citations(report, PROFILE) == []


def test_recommendations_section_has_no_polarity_expectation():
    # recommendations citing a passing check shouldn't be flagged — no polarity check applies
    report = _report(
        recommendations=[GroundedClaim(text="keep it up", citation="dimensions.accessibility.checks.aria_landmarks")]
    )
    assert _validate_citations(report, PROFILE) == []
