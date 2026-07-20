from app.pipeline.rules.base import CheckContext, CheckResult, result


def check(ctx: CheckContext) -> CheckResult:
    sitemap = ctx.crawl.sitemap
    if sitemap.found:
        evidence = f"sitemap found at {sitemap.url!r} (source={sitemap.source}, status={sitemap.status})"
        return result("sitemap_presence", "discoverability", 1.0, evidence, "medium", None)

    evidence = "no sitemap declared in robots.txt and no sitemap.xml at the default path"
    recommendation = "Publish a sitemap.xml (and declare it in robots.txt) so agents/crawlers can enumerate the site's pages without guessing links."
    return result("sitemap_presence", "discoverability", 0.0, evidence, "medium", recommendation)
