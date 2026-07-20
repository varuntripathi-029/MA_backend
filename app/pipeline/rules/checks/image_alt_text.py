from app.pipeline.rules.base import CheckContext, CheckResult, result


def check(ctx: CheckContext) -> CheckResult:
    features = ctx.features
    if features.image_count == 0:
        return result("image_alt_text", "accessibility", 1.0, "no <img> elements on the page", "medium", None)

    coverage = features.alt_text_coverage
    missing = features.image_count - features.images_with_alt_count
    evidence = (
        f"{features.images_with_alt_count}/{features.image_count} images have alt text "
        f"({coverage:.0%} coverage, {missing} missing)"
    )
    recommendation = f"Add descriptive alt text to the {missing} image(s) missing it — agents that can't render pixels rely on this to know what an image shows."
    return result("image_alt_text", "accessibility", coverage, evidence, "medium", recommendation)
