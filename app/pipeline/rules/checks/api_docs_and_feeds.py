import re

from app.pipeline.extractor import FeedLink, LinkInfo
from app.pipeline.rules.base import CheckContext, CheckResult, result
from app.pipeline.rules.link_matching import format_link

API_DOC_PATTERN = re.compile(r"(openapi|swagger|/api\b|api[-\s]?docs?|/developers?\b)", re.IGNORECASE)
FEED_FILE_PATTERN = re.compile(r"(rss\.xml|atom\.xml|/feed/?$)", re.IGNORECASE)


def _describe(entry: LinkInfo | FeedLink) -> str:
    # FeedLink comes from a <link rel="alternate"> tag, which has no anchor
    # text to pair with the href — only <a> tags (LinkInfo) do.
    return format_link(entry) if isinstance(entry, LinkInfo) else entry.href


def check(ctx: CheckContext) -> CheckResult:
    features = ctx.features

    # href-only: this check looks for an actual machine-readable interface
    # (an OpenAPI/swagger spec, a /docs or /developers path), not just the
    # word "developer" appearing incidentally in unrelated anchor text.
    api_matches = [link for link in features.links if API_DOC_PATTERN.search(link.href)]

    feed_matches = list(features.feed_links) + [
        link for link in features.links if FEED_FILE_PATTERN.search(link.href)
    ]

    score = 0.5 * bool(api_matches) + 0.5 * bool(feed_matches)

    evidence = (
        f"API/developer doc links: {[_describe(m) for m in api_matches[:3]] or 'none'}; "
        f"feed links: {[_describe(f) for f in feed_matches[:3]] or 'none'}"
    )
    recommendation = "Link to API/developer documentation (OpenAPI/Swagger spec) and/or expose an RSS/Atom feed — these are the machine-readable interfaces agents look for first."
    return result("api_docs_and_feeds", "discoverability", score, evidence, "low", recommendation)
