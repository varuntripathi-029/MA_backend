"""Module 2: HTML Cleaner.

Strips scripts, styles, ads/tracking, comments, SVGs, hidden nodes, and
duplicate nodes from rendered HTML. Output is a clean BeautifulSoup DOM that
Module 3 (Feature Extractor) reads from — nothing downstream of Module 3
touches raw HTML again.
"""

from bs4 import BeautifulSoup, Comment

STRIPPED_TAGS = ["style", "svg", "noscript", "template", "iframe"]

# application/ld+json <script> blocks are structured data, not executable
# code — Module 4's structured-data check needs them, so `script` isn't in
# STRIPPED_TAGS; this removes only the non-JSON-LD ones.
JSON_LD_TYPE = "application/ld+json"

# Common ad/tracking network markers seen in class/id attributes.
TRACKING_MARKERS = (
    "google-analytics",
    "googletagmanager",
    "doubleclick",
    "facebook-pixel",
    "hotjar",
    "segment",
    "advert",
    "sponsor",
)


def _is_hidden(tag) -> bool:
    style = (tag.get("style") or "").replace(" ", "").lower()
    if "display:none" in style or "visibility:hidden" in style:
        return True
    if tag.get("hidden") is not None:
        return True
    aria_hidden = (tag.get("aria-hidden") or "").lower()
    return aria_hidden == "true"


def _is_tracking_node(tag) -> bool:
    haystack = " ".join(
        [
            " ".join(tag.get("class", []) if isinstance(tag.get("class"), list) else [tag.get("class") or ""]),
            tag.get("id") or "",
        ]
    ).lower()
    return any(marker in haystack for marker in TRACKING_MARKERS)


def clean_html(rendered_html: str) -> BeautifulSoup:
    soup = BeautifulSoup(rendered_html, "lxml")

    for tag_name in STRIPPED_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for script in soup.find_all("script"):
        if script.get("type") != JSON_LD_TYPE:
            script.decompose()

    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    for tag in soup.find_all(True):
        if tag.parent is None:
            continue
        if _is_hidden(tag) or _is_tracking_node(tag):
            tag.decompose()

    # Drop exact-duplicate *leaf* nodes (same tag + same text, no child
    # elements), keeping the first occurrence — cheap dedup for repeated
    # boilerplate (e.g. a widget injected twice by a buggy CMS template).
    # Restricted to leaves: a nested wrapper <div> around a single child
    # naturally has the same aggregate get_text() as that child, so applying
    # this to non-leaf nodes would decompose an ancestor of the very content
    # it wraps and wipe out the whole subtree.
    seen: set[tuple[str, str]] = set()
    for tag in soup.find_all(True):
        if tag.parent is None or tag.find(True) is not None:
            continue
        key = (tag.name, tag.get_text(strip=True))
        if key[1] and key in seen:
            tag.decompose()
        else:
            seen.add(key)

    return soup
