"""Manual end-to-end check of Modules 1-8 against a real URL.

Usage: python scripts/test_pipeline.py https://example.com
"""

import asyncio
import json
import sys
from dataclasses import asdict

sys.path.insert(0, ".")

from app.pipeline.runner import run_pipeline


async def main(url: str) -> None:
    result = await run_pipeline(url)

    print("=== Crawl Result (metadata only, HTML omitted) ===")
    crawl_dict = asdict(result.crawl)
    crawl_dict.pop("rendered_html")
    print(json.dumps(crawl_dict, indent=2))
    print(f"rendered_html length: {len(result.crawl.rendered_html)} chars")

    print("\n=== Extracted Features JSON ===")
    print(json.dumps(result.features.to_dict(), indent=2)[:6000])

    print("\n=== Rule Engine Results ===")
    for check in result.checks:
        print(json.dumps(check.to_dict(), indent=2))

    total = sum(c.score for c in result.checks)
    print(f"\n=== Summary: {total:.2f} / {len(result.checks)} checks passed-equivalent ===")

    profile_json = json.dumps(result.profile.to_dict(), indent=2)
    print("\n=== Machine Profile JSON (Module 5) ===")
    print(profile_json)
    approx_tokens = len(profile_json) // 4
    print(f"\n=== Machine Profile size: {len(profile_json)} chars (~{approx_tokens} tokens) ===")

    print("\n=== Score (Module 7) ===")
    print(json.dumps(result.score.to_dict(), indent=2))

    print(f"\n=== Recommendations (Module 8): {len(result.recommendations)} item(s), critical first ===")
    for rec in result.recommendations:
        print(json.dumps(rec.to_dict(), indent=2))

    print(f"\n=== LLM Reasoning Report (Module 6, model={result.reasoning.model}) ===")
    print(json.dumps(result.reasoning.report.model_dump(), indent=2))

    if result.reasoning.citation_issues:
        print(f"\n=== Citation validation: {len(result.reasoning.citation_issues)} ISSUE(S) ===")
        for issue in result.reasoning.citation_issues:
            print(f"  [{issue.issue_type}] {issue.section}[{issue.index}]: {issue.claim_text!r}")
            print(f"      citation={issue.citation!r} — {issue.detail}")
    else:
        print("\n=== Citation validation: no issues ===")


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    asyncio.run(main(target_url))
