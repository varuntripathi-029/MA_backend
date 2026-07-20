from app.pipeline.rules.base import CheckContext, CheckResult, result


def _types(blocks: list[dict]) -> list[str]:
    types = []
    for block in blocks:
        t = block.get("@type")
        if isinstance(t, list):
            types.extend(t)
        elif t:
            types.append(t)
    return types


def check(ctx: CheckContext) -> CheckResult:
    features = ctx.features
    if features.json_ld_blocks:
        types = _types(features.json_ld_blocks)
        evidence = f"{len(features.json_ld_blocks)} JSON-LD block(s) parsed, @type values: {types or 'none declared'}"
        return result("json_ld_structured_data", "structured_data", 1.0, evidence, "high", None)

    if features.json_ld_raw_count > 0:
        evidence = f"{features.json_ld_raw_count} <script type=\"application/ld+json\"> tag(s) found but none parsed as valid JSON"
        recommendation = "Fix the malformed JSON-LD block(s) — invalid JSON means agents/crawlers that parse structured data get nothing usable."
        return result("json_ld_structured_data", "structured_data", 0.2, evidence, "high", recommendation)

    evidence = "no <script type=\"application/ld+json\"> found"
    recommendation = "Add JSON-LD structured data (schema.org) describing this page/organization/product — it's the most direct machine-readable signal of what the page is."
    return result("json_ld_structured_data", "structured_data", 0.0, evidence, "high", recommendation)
