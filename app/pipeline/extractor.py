"""Module 3: Feature Extractor.

Converts the clean DOM (Module 2 output) into a small structured JSON
object. Everything downstream (Rule Engine onward) operates on this JSON —
raw HTML is never touched again after this step.
"""

import json
import re
from dataclasses import asdict, dataclass

from bs4 import BeautifulSoup

OG_PROPERTY_RE = re.compile(r"^og:")
FEED_TYPES = {"application/rss+xml", "application/atom+xml"}

SEMANTIC_TAGS = [
    "header",
    "nav",
    "main",
    "article",
    "section",
    "aside",
    "footer",
    "figure",
    "figcaption",
    "time",
    "mark",
]


@dataclass
class LinkInfo:
    href: str
    anchor_text: str


@dataclass
class FeedLink:
    href: str
    type: str


@dataclass
class ExtractedFeatures:
    title: str | None
    meta_description: str | None
    headings: dict[str, list[str]]
    button_count: int
    form_count: int
    nav_item_count: int
    image_count: int
    images_with_alt_count: int
    alt_text_coverage: float
    semantic_tag_counts: dict[str, int]
    links: list[LinkInfo]
    canonical_url: str | None
    meta_robots: str | None
    open_graph: dict[str, str]
    json_ld_blocks: list[dict]
    json_ld_raw_count: int
    feed_links: list[FeedLink]
    aria_attribute_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def extract_features(soup: BeautifulSoup) -> ExtractedFeatures:
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = (meta_desc_tag.get("content") or "").strip() if meta_desc_tag else None

    headings = {
        f"h{level}": [h.get_text(strip=True) for h in soup.find_all(f"h{level}")]
        for level in range(1, 7)
    }

    button_count = (
        len(soup.find_all("button"))
        + len(soup.find_all("input", attrs={"type": "submit"}))
        + len(soup.find_all("input", attrs={"type": "button"}))
    )

    form_count = len(soup.find_all("form"))

    nav_item_count = sum(len(nav.find_all("a")) for nav in soup.find_all("nav"))

    images = soup.find_all("img")
    image_count = len(images)
    images_with_alt_count = sum(1 for img in images if (img.get("alt") or "").strip())
    alt_text_coverage = round(images_with_alt_count / image_count, 4) if image_count else 1.0

    semantic_tag_counts = {tag: len(soup.find_all(tag)) for tag in SEMANTIC_TAGS}

    links = [
        LinkInfo(href=a["href"], anchor_text=a.get_text(strip=True))
        for a in soup.find_all("a", href=True)
    ]

    canonical_tag = soup.find("link", rel="canonical")
    canonical_url = canonical_tag.get("href") if canonical_tag else None

    meta_robots_tag = soup.find("meta", attrs={"name": "robots"})
    meta_robots = (meta_robots_tag.get("content") or "").strip() if meta_robots_tag else None

    open_graph = {}
    for tag in soup.find_all("meta", attrs={"property": OG_PROPERTY_RE}):
        prop, content = tag.get("property"), tag.get("content")
        if prop and content:
            open_graph[prop] = content

    json_ld_blocks: list[dict] = []
    json_ld_raw_count = 0
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        json_ld_raw_count += 1
        try:
            data = json.loads(script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            json_ld_blocks.append(data)
        elif isinstance(data, list):
            json_ld_blocks.extend(item for item in data if isinstance(item, dict))

    feed_links = [
        FeedLink(href=link["href"], type=link.get("type"))
        for link in soup.find_all("link", rel="alternate", href=True)
        if link.get("type") in FEED_TYPES
    ]

    aria_attribute_count = sum(
        1
        for tag in soup.find_all(True)
        if any(attr == "role" or attr.startswith("aria-") for attr in tag.attrs)
    )

    return ExtractedFeatures(
        title=title,
        meta_description=meta_description,
        headings=headings,
        button_count=button_count,
        form_count=form_count,
        nav_item_count=nav_item_count,
        image_count=image_count,
        images_with_alt_count=images_with_alt_count,
        alt_text_coverage=alt_text_coverage,
        semantic_tag_counts=semantic_tag_counts,
        links=links,
        canonical_url=canonical_url,
        meta_robots=meta_robots,
        open_graph=open_graph,
        json_ld_blocks=json_ld_blocks,
        json_ld_raw_count=json_ld_raw_count,
        feed_links=feed_links,
        aria_attribute_count=aria_attribute_count,
    )
