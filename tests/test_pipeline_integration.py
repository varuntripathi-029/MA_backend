"""One integration test: Modules 1-8 end to end against a local HTML
fixture. Module 1 (network crawl) and Module 6 (Groq call) are the only
non-deterministic/network-touching pieces of the pipeline, so both are
patched to return canned results — everything else (clean, extract, rules,
profile, score, recommendations) runs for real. Fast, offline, non-flaky."""

from app.pipeline import runner
from app.pipeline.reasoning import GroundedClaim, ReasoningReport, ReasoningResult

from .fixtures import GOOD_HTML, make_crawl_result


async def _fake_crawl(url: str):
    result = make_crawl_result(requested_url=url)
    result.rendered_html = GOOD_HTML
    return result


async def _fake_generate_report(profile: dict, model: str | None = None) -> ReasoningResult:
    report = ReasoningReport(
        purpose="Acme sells widgets online.",
        target_users=["Online shoppers"],
        agent_strengths=[GroundedClaim(text="Clear title and metadata", citation="content.title")],
        agent_weaknesses=[],
        missing_information=[],
        confidence=0.8,
        recommendations=[],
    )
    return ReasoningResult(report=report, citation_issues=[], model="fake-model")


async def test_full_pipeline_end_to_end(monkeypatch):
    monkeypatch.setattr(runner, "crawl", _fake_crawl)
    monkeypatch.setattr(runner, "generate_report", _fake_generate_report)

    result = await runner.run_pipeline("https://acme.example/")

    assert result.crawl.requested_url == "https://acme.example/"
    assert len(result.checks) == 13

    profile_dict = result.profile.to_dict()
    assert set(profile_dict["dimensions"]) == {
        "structure",
        "metadata",
        "accessibility",
        "structured_data",
        "trust",
        "discoverability",
    }

    assert 0.0 <= result.score.overall_score <= 100.0
    assert len(result.score.dimensions) == 6

    # GOOD_HTML passes every check, so no recommendations should fire
    assert result.recommendations == []

    assert result.reasoning.model == "fake-model"
    assert result.reasoning.citation_issues == []
    assert result.reasoning.report.purpose.startswith("Acme")
