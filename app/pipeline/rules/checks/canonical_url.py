from app.pipeline.rules.base import CheckContext, CheckResult, result


def check(ctx: CheckContext) -> CheckResult:
    canonical = ctx.features.canonical_url
    if canonical:
        return result("canonical_url", "metadata", 1.0, f"canonical_url={canonical!r}", "low", None)

    evidence = "no <link rel=\"canonical\"> found"
    recommendation = "Add a <link rel=\"canonical\"> pointing to the preferred URL for this page to avoid duplicate-content ambiguity."
    return result("canonical_url", "metadata", 0.0, evidence, "low", recommendation)
