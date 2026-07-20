from app.pipeline.rules.base import CheckContext, CheckResult, result


def check(ctx: CheckContext) -> CheckResult:
    status = ctx.crawl.http_status
    if status == 200:
        return result("http_status", "trust", 1.0, f"HTTP {status}", "critical", None)

    evidence = f"HTTP {status} (final_url={ctx.crawl.final_url!r})"
    recommendation = f"Return HTTP 200 for this URL — a {status} response tells agents the page may be broken, redirected, or inaccessible, and many will refuse to process it further."
    return result("http_status", "trust", 0.0, evidence, "critical", recommendation)
