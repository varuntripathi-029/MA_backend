from app.pipeline.rules.base import CheckContext, CheckResult, result

MIN_DESCRIPTION_LENGTH = 50
MAX_DESCRIPTION_LENGTH = 300


def check(ctx: CheckContext) -> CheckResult:
    title = ctx.features.title
    description = ctx.features.meta_description

    score = 0.0
    notes = []

    if title:
        score += 0.5
        notes.append(f"title={title!r}")
    else:
        notes.append("title=missing")

    if description and MIN_DESCRIPTION_LENGTH <= len(description) <= MAX_DESCRIPTION_LENGTH:
        score += 0.5
        notes.append(f"meta_description={description!r} ({len(description)} chars)")
    elif description:
        score += 0.25
        notes.append(f"meta_description={description!r} ({len(description)} chars, outside {MIN_DESCRIPTION_LENGTH}-{MAX_DESCRIPTION_LENGTH} recommended range)")
    else:
        notes.append("meta_description=missing")

    evidence = "; ".join(notes)
    recommendation = (
        "Add a <title> and a meta description ("
        f"{MIN_DESCRIPTION_LENGTH}-{MAX_DESCRIPTION_LENGTH} chars) that concisely "
        "state what the page is and does — this is often the first signal an "
        "agent reads to decide whether to process the rest of the page."
    )
    return result("title_and_meta_description", "metadata", score, evidence, "high", recommendation)
