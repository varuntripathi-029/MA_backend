"""Module 1: Crawl Service.

Fetches exactly one URL with Playwright and captures raw fetching/rendering/
gating signals only: rendered HTML, HTTP status, response headers, SSL info,
the robots.txt allow/disallow gate, and sitemap.xml presence. No structured
extraction happens here — that's Module 3's job, run against the cleaned DOM.
"""

import asyncio
import socket
import ssl
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from playwright.async_api import async_playwright

USER_AGENT = "MXRatingBot/0.1 (+https://mxrating.example/bot)"


class CrawlError(Exception):
    pass


@dataclass
class SitemapInfo:
    found: bool
    url: str | None
    source: str | None  # "robots.txt" | "default_path" | None
    status: int | None


@dataclass
class CrawlResult:
    requested_url: str
    final_url: str
    http_status: int
    response_headers: dict[str, str]
    rendered_html: str
    robots_allowed: bool
    sitemap: SitemapInfo
    ssl_info: dict
    fetched_at: str


async def _fetch_robots_txt(url: str) -> str | None:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(robots_url, headers={"User-Agent": USER_AGENT})
            if resp.status_code == 200:
                return resp.text
    except httpx.HTTPError:
        pass
    return None


def _parse_robots(robots_text: str | None, url: str) -> tuple[bool, list[str]]:
    """Returns (allowed, sitemap_urls_declared_in_robots_txt)."""
    if robots_text is None:
        # robots.txt missing/unreachable -> treat as allowed, per common crawler convention
        return True, []

    lines = robots_text.splitlines()
    parser = RobotFileParser()
    parser.parse(lines)
    sitemap_urls = [
        line.split(":", 1)[1].strip()
        for line in lines
        if line.strip().lower().startswith("sitemap:")
    ]
    return parser.can_fetch(USER_AGENT, url), sitemap_urls


async def _check_sitemap(url: str, sitemap_urls_from_robots: list[str]) -> SitemapInfo:
    parsed = urlparse(url)
    default_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    candidates = sitemap_urls_from_robots + (
        [default_url] if default_url not in sitemap_urls_from_robots else []
    )

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for candidate in candidates:
            try:
                resp = await client.head(candidate, headers={"User-Agent": USER_AGENT})
                if resp.status_code == 405:
                    resp = await client.get(candidate, headers={"User-Agent": USER_AGENT})
                if resp.status_code == 200:
                    source = "robots.txt" if candidate in sitemap_urls_from_robots else "default_path"
                    return SitemapInfo(found=True, url=candidate, source=source, status=resp.status_code)
            except httpx.HTTPError:
                continue

    return SitemapInfo(found=False, url=None, source=None, status=None)


def _get_ssl_info(hostname: str) -> dict:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                return {
                    "https": True,
                    "valid": True,
                    "issuer": dict(x[0] for x in cert.get("issuer", ())),
                    "not_after": cert.get("notAfter"),
                    "protocol": ssock.version(),
                }
    except Exception as e:
        return {"https": True, "valid": False, "error": str(e)}


async def _render_page(url: str, timeout_ms: int) -> tuple[str, str, int, dict[str, str]]:
    """The actual Playwright work — isolated so it can be run on a thread
    with a guaranteed-correct dedicated event loop (see _render_page_sync).
    Playwright's async API needs asyncio subprocess support for its browser
    driver, which only ProactorEventLoop provides on Windows."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page(user_agent=USER_AGENT)
            try:
                response = await page.goto(url, wait_until="load", timeout=timeout_ms)
            except Exception as e:
                raise CrawlError(f"Failed to load {url}: {e}") from e

            # Best-effort extra settle time for client-rendered content; don't
            # fail the whole crawl if the page never goes fully idle.
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            html = await page.content()
            final_url = page.url
            status = response.status if response else 0
            headers = dict(response.headers) if response else {}
        finally:
            await browser.close()

    return html, final_url, status, headers


def _render_page_sync(url: str, timeout_ms: int) -> tuple[str, str, int, dict[str, str]]:
    """Runs on a dedicated worker thread (see crawl()) with its own freshly
    created event loop, explicitly Proactor on Windows. Relying on whatever
    loop happens to be ambient in the calling process has proven unreliable
    in practice — uvicorn's --reload supervisor was observed landing worker
    processes on a Selector loop on Windows even with the policy pinned at
    app startup (app/main.py), which broke Playwright's subprocess launch
    with NotImplementedError. A dedicated loop, created here, sidesteps that
    regardless of what the host process's main loop is doing."""
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_render_page(url, timeout_ms))
    finally:
        loop.close()


async def crawl(url: str, timeout_ms: int = 30000) -> CrawlResult:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise CrawlError(f"Unsupported URL scheme: {parsed.scheme!r}")

    robots_text = await _fetch_robots_txt(url)
    robots_allowed, sitemap_urls_from_robots = _parse_robots(robots_text, url)
    if not robots_allowed:
        raise CrawlError(f"{url} is disallowed by robots.txt for {USER_AGENT!r}")

    sitemap_info = await _check_sitemap(url, sitemap_urls_from_robots)

    html, final_url, status, headers = await asyncio.to_thread(_render_page_sync, url, timeout_ms)

    ssl_info = {"https": False}
    if parsed.scheme == "https":
        ssl_info = _get_ssl_info(parsed.hostname or parsed.netloc)

    return CrawlResult(
        requested_url=url,
        final_url=final_url,
        http_status=status,
        response_headers=headers,
        rendered_html=html,
        robots_allowed=robots_allowed,
        sitemap=sitemap_info,
        ssl_info=ssl_info,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
