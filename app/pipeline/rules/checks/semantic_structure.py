from app.pipeline.rules.base import CheckContext, CheckResult, result

LANDMARK_TAGS = ("header", "nav", "main", "footer")


def check(ctx: CheckContext) -> CheckResult:
    counts = ctx.features.semantic_tag_counts
    present = [tag for tag in LANDMARK_TAGS if counts.get(tag, 0) > 0]
    missing = [tag for tag in LANDMARK_TAGS if tag not in present]
    score = len(present) / len(LANDMARK_TAGS)

    evidence = f"landmark tags present: {present or 'none'}; missing: {missing or 'none'} (counts: {counts})"
    recommendation = (
        f"Add semantic landmark elements for {missing} so agents parsing the "
        f"DOM (not just rendered pixels) can locate the page's structural regions."
    )
    return result("semantic_structure", "structure", score, evidence, "medium", recommendation)
