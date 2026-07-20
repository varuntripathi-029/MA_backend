"""Module 4: Rule Engine.

Pure deterministic code, no LLM. Runs every registered check against a
CheckContext and returns their results — nothing here inspects raw HTML,
only Module 1's crawl signals and Module 3's extracted JSON.
"""

from app.pipeline.crawler import CrawlResult
from app.pipeline.extractor import ExtractedFeatures
from app.pipeline.rules.base import CheckContext, CheckResult
from app.pipeline.rules.checks import (
    api_docs_and_feeds,
    aria_landmarks,
    canonical_url,
    heading_hierarchy,
    http_status,
    image_alt_text,
    json_ld,
    link_discoverability,
    metadata,
    open_graph,
    semantic_structure,
    sitemap_presence,
    ssl_validity,
)

CHECKS = (
    semantic_structure.check,
    heading_hierarchy.check,
    metadata.check,
    open_graph.check,
    canonical_url.check,
    image_alt_text.check,
    aria_landmarks.check,
    json_ld.check,
    http_status.check,
    ssl_validity.check,
    sitemap_presence.check,
    api_docs_and_feeds.check,
    link_discoverability.check,
)


def run_checks(features: ExtractedFeatures, crawl: CrawlResult) -> list[CheckResult]:
    ctx = CheckContext(features=features, crawl=crawl)
    return [check_fn(ctx) for check_fn in CHECKS]
