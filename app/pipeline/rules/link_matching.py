"""Shared keyword-matching helper for link-based checks.

Href matches are preferred over anchor-text matches: an href path segment
like /docs or /pricing is a much stronger signal than an incidental keyword
appearing in unrelated anchor text (e.g. a customer-story blurb that happens
to mention "developer").
"""

import re

from app.pipeline.extractor import LinkInfo


def find_best_match(links: list[LinkInfo], pattern: re.Pattern) -> LinkInfo | None:
    href_match = next((link for link in links if pattern.search(link.href)), None)
    if href_match:
        return href_match
    return next((link for link in links if pattern.search(link.anchor_text)), None)


def format_link(link: LinkInfo) -> str:
    """Evidence formatting shared by link-based checks: pair the anchor text
    with the href so evidence is human-checkable, not just a bare URL."""
    anchor = link.anchor_text.strip() or "(no anchor text)"
    return f'"{anchor}" -> {link.href}'
