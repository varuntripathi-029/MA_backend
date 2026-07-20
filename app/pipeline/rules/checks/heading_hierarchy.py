from app.pipeline.rules.base import CheckContext, CheckResult, result


def check(ctx: CheckContext) -> CheckResult:
    headings = ctx.features.headings
    h1_list = headings.get("h1", [])
    h1_count = len(h1_list)

    if h1_count == 0:
        evidence = "no <h1> found on the page"
        recommendation = "Add exactly one <h1> stating the page's primary subject."
        return result("heading_hierarchy", "structure", 0.0, evidence, "medium", recommendation)

    if h1_count > 1:
        evidence = f"{h1_count} <h1> elements found: {h1_list}"
        recommendation = (
            "Use a single <h1> per page — multiple top-level headings make it "
            "ambiguous which one is the page's primary subject."
        )
        return result("heading_hierarchy", "structure", 0.5, evidence, "medium", recommendation)

    # Exactly one h1. Check for a level skip further down (e.g. h1 -> h3 with no h2)
    # among levels that actually have content.
    levels_with_content = [level for level in range(1, 7) if headings.get(f"h{level}")]
    skipped = any(
        b - a > 1 for a, b in zip(levels_with_content, levels_with_content[1:])
    )
    if skipped:
        evidence = f"heading levels present: {levels_with_content} (a level is skipped)"
        recommendation = "Avoid skipping heading levels (e.g. h1 straight to h3) — it breaks the document outline agents use to infer structure."
        return result("heading_hierarchy", "structure", 0.7, evidence, "low", recommendation)

    evidence = f"single <h1> ({h1_list[0]!r}), heading levels present: {levels_with_content}"
    return result("heading_hierarchy", "structure", 1.0, evidence, "low", None)
