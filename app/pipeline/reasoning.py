"""Module 6: LLM Reasoning Engine.

The only LLM call in the pipeline (aim.md #3). Takes the Module 5 Machine
Profile JSON as-is and produces a structured, evidence-linked narrative:
purpose, target users, agent strengths/weaknesses, missing information,
confidence, and recommendations. The LLM never sees raw HTML and never
determines the score — it only narrates what the deterministic Rule Engine
already found.

Provider: Groq. Model default is Llama 3.3 70B (llama-3.3-70b-versatile),
configurable via GROQ_MODEL. Groq's strict `json_schema` response-format
mode is NOT supported by the Llama models on Groq today (only by its
openai/gpt-oss-* models) — confirmed against the live API, not assumed from
docs. We use the looser `json_object` mode instead (valid JSON guaranteed,
but not schema-enforced) and do the schema enforcement ourselves via
Pydantic: a JSON parse failure or schema-validation failure both raise
ReasoningOutputError. Nothing here silently falls back to free-text
parsing or swallows a bad response.

Grounding: every claim in agent_strengths / agent_weaknesses /
missing_information / recommendations must carry a `citation` — a dot-path
into the profile object (e.g. "dimensions.accessibility.checks.
image_alt_text"). The prompt enumerates every valid path for the specific
profile being reasoned over, and every returned citation is re-checked
against that same profile after the call. A citation that doesn't resolve
is a hallucination; it's logged and surfaced via ReasoningResult.
citation_issues rather than dropped.

A resolved citation can still be a hallucination in a subtler way: the path
is real, but the claim's polarity contradicts the value at that path (e.g.
an agent_weaknesses claim "no sitemap" citing a check that actually scored
1.0 / severity "info"). We check this too — a citation that resolves but
whose value doesn't support the claim's polarity (positive for
agent_strengths, negative for agent_weaknesses/missing_information) is
logged and surfaced the same way, tagged "polarity_mismatch" instead of
"unresolved_path".
"""

import json
import logging
from dataclasses import dataclass

from groq import AsyncGroq
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

CITATION_SECTIONS = ("agent_strengths", "agent_weaknesses", "missing_information", "recommendations")

# Sections whose claims carry an inherent polarity we can check the cited
# value against. "recommendations" is intentionally excluded — a
# recommendation is inherently about a gap, but it doesn't always cite a
# failing check (e.g. it can cite a dimension score to argue for further
# improvement even on a decent score), so no reliable expectation applies.
POLARITY_EXPECTATION: dict[str, str] = {
    "agent_strengths": "positive",
    "agent_weaknesses": "negative",
    "missing_information": "negative",
}

# A check scoring at/above this (with severity still "info"/"low") reads as
# "fine" for polarity purposes; below it reads as "a real issue". Hand-set,
# not fitted.
POLARITY_THRESHOLD = 0.7

SYSTEM_PROMPT_TEMPLATE = """You are the reasoning engine for MX_rating, a product that scores how \
ready a website is for AI agents (ChatGPT, Claude, Gemini, shopping/coding agents, etc.) to \
discover, understand, and act on it — not a human-facing SEO or UX review.

You are given one input: a "Machine Profile" JSON object already produced by deterministic code \
(site metadata, extracted content signals, and rule-check results grouped by dimension). You never \
see raw HTML, and you never compute or adjust any score — scores in the profile are final.

Your job is to read the Machine Profile and produce a structured narrative: purpose, target users, \
agent strengths, agent weaknesses, missing information, your confidence, and recommendations.

GROUNDING RULE (critical): every entry in agent_strengths, agent_weaknesses, missing_information, \
and recommendations MUST include a "citation" field that is copied verbatim, character for \
character, from the list of valid citation paths below. Do not invent, abbreviate, merge, or \
construct new paths, and do not cite a path that isn't in the list. If you cannot ground a claim in \
one of these exact paths, drop the claim rather than cite an invalid path.

Valid citation paths for this profile:
{catalog}

Output ONLY a single JSON object with exactly this shape — no markdown fences, no commentary, \
no extra keys:
{{
  "purpose": "<one or two sentences on what this site/page is for>",
  "target_users": ["<short label>", ...],
  "agent_strengths": [{{"text": "<claim>", "citation": "<exact path from the list above>"}}, ...],
  "agent_weaknesses": [{{"text": "<claim>", "citation": "<exact path from the list above>"}}, ...],
  "missing_information": [{{"text": "<claim>", "citation": "<exact path from the list above>"}}, ...],
  "confidence": <number between 0.0 and 1.0>,
  "recommendations": [{{"text": "<claim>", "citation": "<exact path from the list above>"}}, ...]
}}
"""


class ReasoningOutputError(Exception):
    """Raised when Groq's response isn't valid JSON or doesn't match the
    expected report schema. Malformed model output is a hard error, not a
    silent bad-parse."""


class GroundedClaim(BaseModel):
    text: str
    citation: str


class ReasoningReport(BaseModel):
    purpose: str
    target_users: list[str]
    agent_strengths: list[GroundedClaim]
    agent_weaknesses: list[GroundedClaim]
    missing_information: list[GroundedClaim]
    confidence: float = Field(ge=0.0, le=1.0)
    recommendations: list[GroundedClaim]


@dataclass
class CitationIssue:
    section: str
    index: int
    claim_text: str
    citation: str
    issue_type: str  # "unresolved_path" | "polarity_mismatch"
    detail: str


@dataclass
class ReasoningResult:
    report: ReasoningReport
    citation_issues: list[CitationIssue]
    model: str

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "report": self.report.model_dump(),
            "citation_issues": [issue.__dict__ for issue in self.citation_issues],
        }


def _citation_catalog(profile: dict) -> list[str]:
    """Every dot-path a citation is allowed to reference for this specific
    profile: top-level site/content fields, each dimension's rollup score,
    and each individual check (the whole check object, so its evidence/
    score/severity/recommendation are all reachable under one citation)."""
    paths = [f"site.{key}" for key in profile.get("site", {})]
    paths += [f"content.{key}" for key in profile.get("content", {})]
    for dim, dim_data in profile.get("dimensions", {}).items():
        paths.append(f"dimensions.{dim}.score")
        for check_id in dim_data.get("checks", {}):
            paths.append(f"dimensions.{dim}.checks.{check_id}")
    return paths


def _resolve_citation(profile: dict, path: str) -> tuple[bool, object]:
    """Walk a dot-path into the profile. Returns (resolved, value) — value is
    None (meaningless) when resolved is False."""
    node = profile
    for segment in path.split("."):
        if not isinstance(node, dict) or segment not in node:
            return False, None
        node = node[segment]
    return True, node


def _polarity_of(value: object) -> bool | None:
    """Best-effort read of whether a resolved citation value is "good" (True)
    or "bad" (False) news for the site, for the citation shapes Module 5
    actually produces. None means this value type has no inherent polarity
    (e.g. a title string, a count) — such citations skip the polarity check
    entirely and are judged on path-resolution alone."""
    if isinstance(value, dict):
        if "score" in value and "severity" in value:  # a check result
            return value["score"] >= POLARITY_THRESHOLD and value["severity"] in ("info", "low")
        if "score" in value and "checks" in value:  # a dimension summary
            return value["score"] >= POLARITY_THRESHOLD
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, list):
        return len(value) > 0
    return None


def _validate_citations(report: ReasoningReport, profile: dict) -> list[CitationIssue]:
    issues = []
    for section in CITATION_SECTIONS:
        expected_polarity = POLARITY_EXPECTATION.get(section)
        for index, claim in enumerate(getattr(report, section)):
            resolved, value = _resolve_citation(profile, claim.citation)
            if not resolved:
                issues.append(
                    CitationIssue(
                        section=section,
                        index=index,
                        claim_text=claim.text,
                        citation=claim.citation,
                        issue_type="unresolved_path",
                        detail="citation path does not resolve in the profile",
                    )
                )
                continue

            if expected_polarity is None:
                continue
            actual_polarity = _polarity_of(value)
            if actual_polarity is None:
                continue
            is_positive = expected_polarity == "positive"
            if actual_polarity != is_positive:
                issues.append(
                    CitationIssue(
                        section=section,
                        index=index,
                        claim_text=claim.text,
                        citation=claim.citation,
                        issue_type="polarity_mismatch",
                        detail=(
                            f"claim reads as {expected_polarity} but the cited value is "
                            f"{'positive' if actual_polarity else 'negative'}: {value!r}"
                        ),
                    )
                )

    for issue in issues:
        logger.warning(
            "%s in %s[%d]: claim %r cites %r — %s",
            issue.issue_type,
            issue.section,
            issue.index,
            issue.claim_text,
            issue.citation,
            issue.detail,
        )
    return issues


async def generate_report(profile: dict, model: str | None = None) -> ReasoningResult:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    model = model or settings.groq_model
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(catalog="\n".join(_citation_catalog(profile)))

    client = AsyncGroq(api_key=settings.groq_api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Machine Profile:\n{json.dumps(profile)}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    raw = response.choices[0].message.content

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ReasoningOutputError(f"Groq returned non-JSON output: {e}\nRaw output: {raw!r}") from e

    try:
        report = ReasoningReport.model_validate(parsed)
    except ValidationError as e:
        raise ReasoningOutputError(f"Groq output didn't match the expected report schema: {e}\nRaw output: {raw!r}") from e

    citation_issues = _validate_citations(report, profile)
    return ReasoningResult(report=report, citation_issues=citation_issues, model=model)
