from app.pipeline.rules.base import CheckContext, CheckResult, result


def check(ctx: CheckContext) -> CheckResult:
    ssl_info = ctx.crawl.ssl_info

    if not ssl_info.get("https"):
        evidence = "site served over plain HTTP, no TLS"
        recommendation = "Serve the site over HTTPS — agents and their platforms increasingly refuse to fetch or transact on plain-HTTP pages."
        return result("ssl_validity", "trust", 0.0, evidence, "critical", recommendation)

    if ssl_info.get("valid"):
        evidence = f"valid TLS cert, issuer={ssl_info.get('issuer')}, protocol={ssl_info.get('protocol')}, expires={ssl_info.get('not_after')}"
        return result("ssl_validity", "trust", 1.0, evidence, "critical", None)

    evidence = f"HTTPS present but certificate invalid: {ssl_info.get('error')}"
    recommendation = "Fix the invalid/expired TLS certificate — agents that validate certs will fail the connection outright."
    return result("ssl_validity", "trust", 0.0, evidence, "critical", recommendation)
