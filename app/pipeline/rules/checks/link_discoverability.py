"""Homepage link discoverability — the deterministic, cheap substitute for
the cut Agent Simulator (see aim.md #4, plan.md Module 4). Only inspects
links already present in Module 3's page-wide link list; never fetches or
follows a link (depth-1 only, single-page scan per aim.md #5)."""

import re

from app.pipeline.rules.base import CheckContext, CheckResult, result
from app.pipeline.rules.link_matching import find_best_match, format_link

CATEGORIES: dict[str, re.Pattern] = {
    "pricing/plans": re.compile(r"pric(e|ing)|\bplans?\b", re.IGNORECASE),
    "docs/api/developers": re.compile(r"\bdocs?\b|documentation|\bapi\b|developers?", re.IGNORECASE),
    "contact/support": re.compile(r"contact|support|\bhelp\b", re.IGNORECASE),
    "signup/login": re.compile(r"sign[\s-]?up|log[\s-]?in|sign[\s-]?in|register|get started|create account", re.IGNORECASE),
}


def check(ctx: CheckContext) -> CheckResult:
    links = ctx.features.links

    found = {category: find_best_match(links, pattern) for category, pattern in CATEGORIES.items()}

    matched_count = sum(1 for match in found.values() if match)
    score = matched_count / len(CATEGORIES)

    evidence = "; ".join(
        f"{cat}: {format_link(match) if match else 'not found'}" for cat, match in found.items()
    )
    missing = [cat for cat, match in found.items() if not match]
    recommendation = f"Add a homepage link for: {missing} — an agent scanning only this page's links can't discover these categories otherwise."
    return result("link_discoverability", "discoverability", score, evidence, "high", recommendation)
