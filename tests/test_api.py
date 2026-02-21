from __future__ import annotations

from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import pytest

from pywznab import (
    APIlimits,
    BookRequest,
    Caps,
    CapsRequest,
    Category,
    CategoryTree,
    ErrorCode,
    ExtraElement,
    FeedImage,
    FeedMeta,
    Limits,
    MovieRequest,
    MusicRequest,
    NewznabAPI,
    NewznabError,
    Release,
    SearchRequest,
    SearchResult,
    Searching,
    TvSearchRequest,
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
        searching=Searching(tv=True, movie=True),
        server_url="http://example.test",
        server_email="ops@example.test",
    )
    return NewznabAPI(caps=caps, base_url="http://example.test")


def test_parse_caps_request():
    api = _make_api()
    parsed = api.parse({"t": "caps"})
    assert isinstance(parsed, CapsRequest)


def test_parse_search_limits_and_categories():
    api = _make_api()
    parsed = api.parse({"t": "search", "limit": "1000", "offset": "5", "cat": "5030,2040", "attrs": "size,guid"})
    assert isinstance(parsed, SearchRequest)
    assert parsed.limit == 100
    assert parsed.offset == 5
    assert parsed.categories == [5030, 2040]
    assert parsed.attrs == ["size", "guid"]


def test_parse_tvsearch_filters():
    api = _make_api()
    parsed = api.parse({"t": "tvsearch", "tvdbid": "12345", "season": "2", "ep": "3"})
    assert isinstance(parsed, TvSearchRequest)
    assert parsed.tv is not None
    assert parsed.tv.tvdbid == "12345"
    assert parsed.tv.season == 2
    assert parsed.tv.ep == 3


def test_parse_movie_music_book_filters():
    api = _make_api()

    movie = api.parse({"t": "movie", "q": "python", "imdbid": "tt12345", "genre": "sci-fi"})
    assert isinstance(movie, MovieRequest)
    assert movie.movie is not None
    assert movie.movie.imdbid == "tt12345"
    assert movie.movie.genre == "sci-fi"

    music = api.parse({"t": "music", "artist": "Band", "album": "Album", "year": "2020"})
    assert isinstance(music, MusicRequest)
    assert music.music is not None
    assert music.music.artist == "Band"
    assert music.music.album == "Album"
    assert music.music.year == 2020

    book = api.parse({"t": "book", "title": "Book", "author": "Author"})
    assert isinstance(book, BookRequest)
    assert book.book is not None
    assert book.book.title == "Book"
    assert book.book.author == "Author"


def test_parse_invalid_param():
    api = _make_api()
    with pytest.raises(NewznabError) as exc:
        api.parse({"t": "search", "limit": "nope"})
    assert exc.value.code == ErrorCode.INVALID_PARAMETER

    with pytest.raises(NewznabError) as exc:
        api.parse({"t": "music", "year": "not-a-number"})
    assert exc.value.code == ErrorCode.INVALID_PARAMETER


def test_render_caps_xml():
    api = _make_api()
    xml_text = api.render_caps()
    root = ET.fromstring(xml_text)
    assert root.tag == "caps"
    assert root.find("server").get("title") == "pywznab tests"
    assert root.find("server").get("email") == "ops@example.test"
    assert root.find("searching").find("movie-search").get("available") == "yes"
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
        category_name="TV > HD",
        description="PoC",
        nzb_id="guid-1",
        details_url="http://example.test/details/guid-1",
        comments_url="http://example.test/details/guid-1#comments",
        guid_is_permalink=True,
        attrs={"guid": "guid-1", "sha1": "abc123"},
    )
    result = SearchResult(
        total=1,
        offset=0,
        limit=100,
        items=[release],
        feed=FeedMeta(
            self_link="http://example.test/api?t=search&q=pythonic",
            language="en-gb",
            web_master="ops@example.test (pywznab tests)",
            image=FeedImage(
                url="http://example.test/banner.jpg",
                title="pywznab tests",
                link="http://example.test/",
            ),
        ),
        api_limits=APIlimits(apicurrent=1, apimax=100, grabcurrent=2, grabmax=50),
    )
    xml_text = api.render_search(result, attrs=["size", "guid"])
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    assert channel is not None
    assert channel.find("language").text == "en-gb"
    items = channel.findall("item")
    assert len(items) == 1
    assert items[0].find("guid").get("isPermaLink") == "true"
    assert items[0].find("comments").text.endswith("#comments")
    enclosure = items[0].find("enclosure")
    assert enclosure is not None
    assert enclosure.get("type") == "application/x-nzb"
    attrs = {
        (attr.get("name"), attr.get("value"))
        for attr in items[0].findall("{http://www.newznab.com/DTD/2008/feeds/attributes/}attr")
    }
    assert ("size", "1500000000") in attrs
    assert ("guid", "guid-1") in attrs
    assert all(name != "sha1" for name, _ in attrs)


def test_render_search_supports_custom_extra_elements():
    api = _make_api()
    release = Release(
        guid="guid-2",
        title="Custom.Release",
        pubdate=datetime(2026, 1, 31, tzinfo=timezone.utc),
        size=123,
        category=5030,
        description="custom",
        nzb_id="guid-2",
        extra_elements=(
            ExtraElement(
                tag="{urn:custom:item}meta",
                attrs={"k": "v"},
                text="item-extra",
            ),
        ),
    )
    result = SearchResult(
        total=1,
        offset=0,
        limit=100,
        items=[release],
        extra_channel_elements=(
            ExtraElement(
                tag="{urn:custom:channel}flag",
                text="channel-extra",
            ),
        ),
    )
    xml_text = api.render_search(result)
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    assert channel is not None
    channel_extra = channel.find("{urn:custom:channel}flag")
    assert channel_extra is not None
    assert channel_extra.text == "channel-extra"
    item = channel.find("item")
    assert item is not None
    item_extra = item.find("{urn:custom:item}meta")
    assert item_extra is not None
    assert item_extra.get("k") == "v"
    assert item_extra.text == "item-extra"
