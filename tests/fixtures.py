"""Small, local, hand-written fixtures for the deterministic pipeline
modules. No network calls — HTML is inline, CrawlResult fields are
constructed directly."""

from app.pipeline.crawler import CrawlResult, SitemapInfo

GOOD_HTML = """
<html>
<head>
  <title>Acme Widgets — buy widgets online</title>
  <meta name="description" content="Acme sells high-quality widgets for every use case.">
  <link rel="canonical" href="https://acme.example/">
  <meta property="og:title" content="Acme Widgets">
  <meta property="og:description" content="Buy widgets online">
  <meta property="og:image" content="https://acme.example/og.png">
  <meta property="og:type" content="website">
  <link rel="alternate" type="application/rss+xml" href="/feed.xml">
  <script type="application/ld+json">{"@context": "https://schema.org", "@type": "Organization", "name": "Acme"}</script>
</head>
<body>
  <header><nav><a href="/pricing">Pricing</a><a href="/api-docs">API Docs</a><a href="/contact">Contact</a><a href="/signup">Sign up</a></nav></header>
  <main>
    <h1>Acme Widgets</h1>
    <h2>Why choose us</h2>
    <p>We make widgets.</p>
    <img src="/widget.png" alt="A blue widget on a white background">
    <button role="button">Buy now</button>
    <form aria-label="Newsletter signup"><input type="email"></form>
  </main>
  <footer>Acme Inc.</footer>
</body>
</html>
"""

BAD_HTML = """
<html>
<head><title></title></head>
<body>
  <div>
    <div>
      <div>No headings, no semantic tags, no metadata.</div>
      <img src="/a.png">
      <img src="/b.png">
      <a href="/x">click here</a>
    </div>
  </div>
</body>
</html>
"""


def make_crawl_result(
    *,
    requested_url: str = "https://acme.example/",
    http_status: int = 200,
    https: bool = True,
    ssl_valid: bool = True,
    robots_allowed: bool = True,
    sitemap_found: bool = True,
) -> CrawlResult:
    return CrawlResult(
        requested_url=requested_url,
        final_url=requested_url,
        http_status=http_status,
        response_headers={},
        rendered_html="",
        robots_allowed=robots_allowed,
        sitemap=SitemapInfo(
            found=sitemap_found,
            url=f"{requested_url}sitemap.xml" if sitemap_found else None,
            source="default_path" if sitemap_found else None,
            status=200 if sitemap_found else None,
        ),
        ssl_info={"https": https, "valid": ssl_valid, "issuer": {"O": "Test CA"}, "not_after": "Jan 1 2030", "protocol": "TLSv1.3"}
        if https
        else {"https": False},
        fetched_at="2026-01-01T00:00:00+00:00",
    )
