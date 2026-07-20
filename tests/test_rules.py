"""Unit tests for Module 4 (Rule Engine) against small local HTML fixtures.
No network calls — clean_html/extract_features run on inline HTML strings."""

from app.pipeline.cleaner import clean_html
from app.pipeline.extractor import extract_features
from app.pipeline.rules.base import CheckContext
from app.pipeline.rules.checks import (
    aria_landmarks,
    canonical_url,
    heading_hierarchy,
    http_status,
    image_alt_text,
    json_ld,
    metadata,
    open_graph,
    semantic_structure,
    sitemap_presence,
    ssl_validity,
)
from app.pipeline.rules.engine import run_checks

from .fixtures import BAD_HTML, GOOD_HTML, make_crawl_result


def _ctx(html: str, **crawl_kwargs) -> CheckContext:
    features = extract_features(clean_html(html))
    crawl = make_crawl_result(**crawl_kwargs)
    return CheckContext(features=features, crawl=crawl)


def test_semantic_structure_rewards_landmark_tags():
    good = semantic_structure.check(_ctx(GOOD_HTML))
    bad = semantic_structure.check(_ctx(BAD_HTML))
    assert good.score > bad.score
    assert bad.severity != "info"
    assert bad.recommendation is not None


def test_heading_hierarchy_passes_with_single_h1():
    good = heading_hierarchy.check(_ctx(GOOD_HTML))
    assert good.score == 1.0
    assert good.severity == "info"


def test_heading_hierarchy_fails_with_no_headings():
    bad = heading_hierarchy.check(_ctx(BAD_HTML))
    assert bad.score < 1.0


def test_title_and_meta_description_present():
    good = metadata.check(_ctx(GOOD_HTML))
    assert good.score == 1.0
    bad = metadata.check(_ctx(BAD_HTML))
    assert bad.score < 1.0
    assert "meta description" in bad.recommendation.lower()


def test_open_graph_full_set_passes():
    good = open_graph.check(_ctx(GOOD_HTML))
    assert good.score == 1.0
    bad = open_graph.check(_ctx(BAD_HTML))
    assert bad.score == 0.0


def test_canonical_url_present_vs_absent():
    assert canonical_url.check(_ctx(GOOD_HTML)).score == 1.0
    assert canonical_url.check(_ctx(BAD_HTML)).score == 0.0


def test_image_alt_text_coverage():
    good = image_alt_text.check(_ctx(GOOD_HTML))
    assert good.score == 1.0  # the one <img> has alt text
    bad = image_alt_text.check(_ctx(BAD_HTML))
    assert bad.score == 0.0  # neither <img> has alt text


def test_aria_landmarks_detects_role_attribute():
    good = aria_landmarks.check(_ctx(GOOD_HTML))
    assert good.score == 1.0
    bad = aria_landmarks.check(_ctx(BAD_HTML))
    assert bad.score == 0.0


def test_json_ld_present_vs_absent():
    good = json_ld.check(_ctx(GOOD_HTML))
    assert good.score == 1.0
    bad = json_ld.check(_ctx(BAD_HTML))
    assert bad.score == 0.0


def test_http_status_ok_vs_error():
    ok = http_status.check(_ctx(GOOD_HTML, http_status=200))
    assert ok.score == 1.0
    err = http_status.check(_ctx(GOOD_HTML, http_status=500))
    assert err.score == 0.0
    assert err.severity == "critical"


def test_ssl_validity_plain_http_fails():
    plain_http = ssl_validity.check(_ctx(GOOD_HTML, https=False))
    assert plain_http.score == 0.0
    valid = ssl_validity.check(_ctx(GOOD_HTML, https=True, ssl_valid=True))
    assert valid.score == 1.0
    invalid = ssl_validity.check(_ctx(GOOD_HTML, https=True, ssl_valid=False))
    assert invalid.score == 0.0


def test_sitemap_presence():
    found = sitemap_presence.check(_ctx(GOOD_HTML, sitemap_found=True))
    assert found.score == 1.0
    missing = sitemap_presence.check(_ctx(GOOD_HTML, sitemap_found=False))
    assert missing.score == 0.0


def test_run_checks_covers_all_dimensions():
    features = extract_features(clean_html(GOOD_HTML))
    crawl = make_crawl_result()
    checks = run_checks(features, crawl)

    dimensions = {c.dimension for c in checks}
    assert dimensions == {
        "structure",
        "metadata",
        "accessibility",
        "structured_data",
        "trust",
        "discoverability",
    }
    assert len(checks) == 13
    # every check produced a valid CheckResult shape
    for c in checks:
        assert 0.0 <= c.score <= 1.0
        assert (c.score >= 1.0) == (c.severity == "info")
        assert (c.score >= 1.0) == (c.recommendation is None)
