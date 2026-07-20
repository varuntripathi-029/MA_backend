from app.pipeline.rules.base import CheckContext, CheckResult, result


def check(ctx: CheckContext) -> CheckResult:
    count = ctx.features.aria_attribute_count
    if count > 0:
        return result("aria_landmarks", "accessibility", 1.0, f"{count} elements carry an ARIA role/attribute", "low", None)

    evidence = "no elements with a `role` or `aria-*` attribute found"
    recommendation = "Add ARIA roles/attributes to key interactive and structural elements to make page semantics explicit for assistive tech and agents alike."
    return result("aria_landmarks", "accessibility", 0.0, evidence, "low", recommendation)
