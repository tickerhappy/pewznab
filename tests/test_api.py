from __future__ import annotations

from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import pytest

from pywznab import (
    Caps,
    Category,
    CategoryTree,
    ErrorCode,
    Limits,
    NewznabAPI,
    NewznabError,
    Release,
    SearchResult,
    Searching,
)


def _make_api() -> NewznabAPI:
    caps = Caps(
        server_title="pywznab tests",
        limits=Limits(default=50, max=100),
        categories=CategoryTree(
            [
                Category(5000, "TV", [Category(5030, "HD")]),
                Category(2000, "Movies", [Category(2040, "HD")]),
            ]
        ),
        searching=Searching(tv=True),
    )
    return NewznabAPI(caps=caps, base_url="http://example.test")


def test_parse_caps_request():
    api = _make_api()
    parsed = api.parse({"t": "caps"})
    assert parsed.type == "caps"


def test_parse_search_limits_and_categories():
    api = _make_api()
    parsed = api.parse({"t": "search", "limit": "1000", "offset": "5", "cat": "5030,2040"})
    assert parsed.limit == 100
    assert parsed.offset == 5
    assert parsed.categories == [5030, 2040]


def test_parse_invalid_param():
    api = _make_api()
    with pytest.raises(NewznabError) as exc:
        api.parse({"t": "search", "limit": "nope"})
    assert exc.value.code == ErrorCode.INVALID_PARAMETER


def test_render_caps_xml():
    api = _make_api()
    xml_text = api.render_caps()
    root = ET.fromstring(xml_text)
    assert root.tag == "caps"
    assert root.find("server").get("title") == "pywznab tests"
    categories = root.find("categories")
    assert categories is not None
    tv_cat = categories.find("category")
    assert tv_cat is not None
    assert tv_cat.get("id") == "5000"


def test_render_search_xml_contains_items():
    api = _make_api()
    release = Release(
        guid="guid-1",
        title="The.Pythonic.S01E01.1080p.WEB-DL-GROUP",
        pubdate=datetime(2026, 1, 31, tzinfo=timezone.utc),
        size=1_500_000_000,
        category=5030,
        description="PoC",
        nzb_id="guid-1",
    )
    result = SearchResult(total=1, offset=0, limit=100, items=[release])
    xml_text = api.render_search(result)
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    assert channel is not None
    items = channel.findall("item")
    assert len(items) == 1
    enclosure = items[0].find("enclosure")
    assert enclosure is not None
    assert enclosure.get("type") == "application/x-nzb"
