from app.pipeline.rules.base import CheckContext, CheckResult, result

KEY_OG_TAGS = ("og:title", "og:description", "og:image", "og:type")


def check(ctx: CheckContext) -> CheckResult:
    og = ctx.features.open_graph
    present = [tag for tag in KEY_OG_TAGS if tag in og]
    missing = [tag for tag in KEY_OG_TAGS if tag not in og]
    score = len(present) / len(KEY_OG_TAGS)

    evidence = f"present: { {tag: og[tag] for tag in present} or 'none'}; missing: {missing or 'none'}"
    recommendation = f"Add Open Graph tags for {missing} — many agents and link previewers read these before falling back to page content."
    return result("open_graph", "metadata", score, evidence, "low", recommendation)
