"""Module 5: Machine Profile Builder.

Merges Module 3's extracted features and Module 4's rule check results into
one structured Machine Profile JSON object per scanned site — the object
Module 6 (LLM Reasoning Engine) consumes directly. Pure data-shaping: no new
extraction or scoring logic lives here.

Two things this is deliberately NOT:
- A raw nesting of the two source objects. `content` is a tight digest (full
  link lists / per-heading-level text stay back in Module 3's output; Module
  6 reasons over labels and counts, not link dumps) so the profile stays
  close to the ~700-token budget aim.md sets for the Module 6 call.
- A flattening of the rule checks. Each check's dimension/score/evidence/
  recommendation stays intact under `dimensions[<dimension>].checks[<id>]`
  so Module 6 can cite a specific check by id as evidence for a claim.
"""

from dataclasses import asdict, dataclass

from app.pipeline.crawler import CrawlResult
from app.pipeline.extractor import ExtractedFeatures
from app.pipeline.rules.base import CheckResult


@dataclass
class SiteIdentity:
    requested_url: str
    final_url: str
    http_status: int
    https: bool
    robots_allowed: bool
    sitemap_found: bool
    fetched_at: str


@dataclass
class ContentSummary:
    title: str | None
    meta_description: str | None
    h1_text: list[str]
    heading_counts: dict[str, int]
    nav_item_count: int
    button_count: int
    form_count: int
    total_link_count: int
    image_alt_text_coverage: float
    semantic_tag_counts: dict[str, int]
    canonical_url: str | None
    meta_robots: str | None
    open_graph_title: str | None
    open_graph_description: str | None
    json_ld_types: list[str]
    feed_count: int


@dataclass
class DimensionSummary:
    score: float  # mean of this dimension's check scores, 0.0-1.0
    checks: dict[str, CheckResult]  # keyed by check id — each entry addressable as evidence


@dataclass
class MachineProfile:
    site: SiteIdentity
    content: ContentSummary
    dimensions: dict[str, DimensionSummary]

    def to_dict(self) -> dict:
        return {
            "site": asdict(self.site),
            "content": asdict(self.content),
            "dimensions": {
                dim: {
                    "score": summary.score,
                    "checks": {check_id: check.to_dict() for check_id, check in summary.checks.items()},
                }
                for dim, summary in self.dimensions.items()
            },
        }


def _json_ld_types(blocks: list[dict]) -> list[str]:
    types: list[str] = []
    for block in blocks:
        t = block.get("@type")
        if isinstance(t, str):
            types.append(t)
        elif isinstance(t, list):
            types.extend(str(item) for item in t)
    return types


def build_profile(
    features: ExtractedFeatures, crawl: CrawlResult, checks: list[CheckResult]
) -> MachineProfile:
    site = SiteIdentity(
        requested_url=crawl.requested_url,
        final_url=crawl.final_url,
        http_status=crawl.http_status,
        https=bool(crawl.ssl_info.get("https")),
        robots_allowed=crawl.robots_allowed,
        sitemap_found=crawl.sitemap.found,
        fetched_at=crawl.fetched_at,
    )

    content = ContentSummary(
        title=features.title,
        meta_description=features.meta_description,
        h1_text=features.headings.get("h1", []),
        heading_counts={level: len(texts) for level, texts in features.headings.items()},
        nav_item_count=features.nav_item_count,
        button_count=features.button_count,
        form_count=features.form_count,
        total_link_count=len(features.links),
        image_alt_text_coverage=features.alt_text_coverage,
        semantic_tag_counts=features.semantic_tag_counts,
        canonical_url=features.canonical_url,
        meta_robots=features.meta_robots,
        open_graph_title=features.open_graph.get("og:title"),
        open_graph_description=features.open_graph.get("og:description"),
        json_ld_types=_json_ld_types(features.json_ld_blocks),
        feed_count=len(features.feed_links),
    )

    by_dimension: dict[str, list[CheckResult]] = {}
    for check in checks:
        by_dimension.setdefault(check.dimension, []).append(check)

    dimensions = {
        dim: DimensionSummary(
            score=round(sum(c.score for c in dim_checks) / len(dim_checks), 4),
            checks={c.id: c for c in dim_checks},
        )
        for dim, dim_checks in by_dimension.items()
    }

    return MachineProfile(site=site, content=content, dimensions=dimensions)
