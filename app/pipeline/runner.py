"""Runs Modules 1-8 end to end against a single URL. Used by both the scan
API's background task (app/api/scans.py) and the manual checkpoint script
(scripts/test_pipeline.py), so both exercise the exact same pipeline path."""

from dataclasses import dataclass

from app.pipeline.cleaner import clean_html
from app.pipeline.crawler import CrawlResult, crawl
from app.pipeline.extractor import ExtractedFeatures, extract_features
from app.pipeline.profile import MachineProfile, build_profile
from app.pipeline.reasoning import ReasoningResult, generate_report
from app.pipeline.recommendations import RecommendationItem, build_recommendations
from app.pipeline.rules.base import CheckResult
from app.pipeline.rules.engine import run_checks
from app.pipeline.scoring import ScoreResult, score_profile


@dataclass
class PipelineResult:
    crawl: CrawlResult
    features: ExtractedFeatures
    checks: list[CheckResult]
    profile: MachineProfile
    score: ScoreResult
    recommendations: list[RecommendationItem]
    reasoning: ReasoningResult


async def run_pipeline(url: str) -> PipelineResult:
    crawl_result = await crawl(url)
    soup = clean_html(crawl_result.rendered_html)
    features = extract_features(soup)
    checks = run_checks(features, crawl_result)
    profile = build_profile(features, crawl_result, checks)
    profile_dict = profile.to_dict()

    score = score_profile(profile_dict)
    recs = build_recommendations(checks)
    reasoning = await generate_report(profile_dict)

    return PipelineResult(
        crawl=crawl_result,
        features=features,
        checks=checks,
        profile=profile,
        score=score,
        recommendations=recs,
        reasoning=reasoning,
    )
