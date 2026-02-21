from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Mapping
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from .errors import ErrorCode, NewznabError
from .models import APIlimits, BookFilters, Caps, ExtraElement, MovieFilters, MusicFilters, Release, SearchResult, TvFilters


NEWZNAB_NS = "http://www.newznab.com/DTD/2008/feeds/attributes/"
ATOM_NS = "http://www.w3.org/2005/Atom"

ET.register_namespace("newznab", NEWZNAB_NS)
ET.register_namespace("atom", ATOM_NS)


@dataclass(frozen=True)
class CapsRequest:
    type: str = "caps"


@dataclass(frozen=True)
class SearchRequest:
    q: str | None
    categories: list[int]
    maxage: int | None
    offset: int
    limit: int
    attrs: list[str] | None
    type: str = "search"


@dataclass(frozen=True)
class TvSearchRequest:
    q: str | None
    categories: list[int]
    maxage: int | None
    offset: int
    limit: int
    attrs: list[str] | None
    tv: TvFilters
    type: str = "tvsearch"


@dataclass(frozen=True)
class MovieRequest:
    q: str | None
    categories: list[int]
    maxage: int | None
    offset: int
    limit: int
    attrs: list[str] | None
    movie: MovieFilters
    type: str = "movie"


@dataclass(frozen=True)
class MusicRequest:
    q: str | None
    categories: list[int]
    maxage: int | None
    offset: int
    limit: int
    attrs: list[str] | None
    music: MusicFilters
    type: str = "music"


@dataclass(frozen=True)
class BookRequest:
    q: str | None
    categories: list[int]
    maxage: int | None
    offset: int
    limit: int
    attrs: list[str] | None
    book: BookFilters
    type: str = "book"


NewznabRequest = CapsRequest | SearchRequest | TvSearchRequest | MovieRequest | MusicRequest | BookRequest


class NewznabAPI:
    def __init__(self, *, caps: Caps, base_url: str):
        self.caps = caps
        self.base_url = base_url.rstrip("/")

    def parse(self, params: Mapping[str, str]) -> NewznabRequest:
        request_type = params.get("t")
        if not request_type:
            raise NewznabError(ErrorCode.MISSING_PARAMETER, "Missing parameter: t")

        if request_type not in {"caps", "search", "tvsearch", "movie", "music", "book"}:
            raise NewznabError(ErrorCode.UNSUPPORTED_FUNCTION, f"Unsupported function: {request_type}")

        if request_type == "caps":
            return CapsRequest()

        q = params.get("q") or None
        categories = self._parse_categories(params.get("cat"))
        maxage = self._parse_optional_int(params.get("maxage"), "maxage")
        offset = self._parse_optional_int(params.get("offset"), "offset") or 0
        limit = self._parse_optional_int(params.get("limit"), "limit") or self.caps.limits.default
        attrs = self._parse_attrs(params.get("attrs"))

        if offset < 0:
            raise NewznabError(ErrorCode.INVALID_PARAMETER, "Invalid offset")
        if limit < 0:
            raise NewznabError(ErrorCode.INVALID_PARAMETER, "Invalid limit")
        if limit > self.caps.limits.max:
            limit = self.caps.limits.max

        if request_type == "search":
            return SearchRequest(
                q=q,
                categories=categories,
                maxage=maxage,
                offset=offset,
                limit=limit,
                attrs=attrs,
            )

        if request_type == "tvsearch":
            tv = TvFilters(
                tvdbid=params.get("tvdbid") or None,
                season=self._parse_optional_int(params.get("season"), "season"),
                ep=self._parse_optional_int(params.get("ep"), "ep"),
            )
            if not (q or tv.tvdbid):
                raise NewznabError(ErrorCode.MISSING_PARAMETER, "tvsearch requires q or tvdbid")
            return TvSearchRequest(
                q=q,
                categories=categories,
                maxage=maxage,
                offset=offset,
                limit=limit,
                attrs=attrs,
                tv=tv,
            )

        if request_type == "movie":
            movie = MovieFilters(
                imdbid=params.get("imdbid") or None,
                genre=params.get("genre") or None,
            )
            if not (q or movie.imdbid or movie.genre):
                raise NewznabError(ErrorCode.MISSING_PARAMETER, "movie requires q, imdbid, or genre")
            return MovieRequest(
                q=q,
                categories=categories,
                maxage=maxage,
                offset=offset,
                limit=limit,
                attrs=attrs,
                movie=movie,
            )

        if request_type == "music":
            music = MusicFilters(
                artist=params.get("artist") or None,
                album=params.get("album") or None,
                title=params.get("title") or None,
                label=params.get("label") or None,
                track=params.get("track") or None,
                year=self._parse_optional_int(params.get("year"), "year"),
                genre=params.get("genre") or None,
            )
            if not (
                q
                or music.artist
                or music.album
                or music.title
                or music.label
                or music.track
                or music.year is not None
                or music.genre
            ):
                raise NewznabError(
                    ErrorCode.MISSING_PARAMETER,
                    "music requires q, artist, album, title, label, track, year, or genre",
                )
            return MusicRequest(
                q=q,
                categories=categories,
                maxage=maxage,
                offset=offset,
                limit=limit,
                attrs=attrs,
                music=music,
            )

        book = BookFilters(
            title=params.get("title") or None,
            author=params.get("author") or None,
        )
        if not (q or book.title or book.author):
            raise NewznabError(ErrorCode.MISSING_PARAMETER, "book requires q, title, or author")
        return BookRequest(
            q=q,
            categories=categories,
            maxage=maxage,
            offset=offset,
            limit=limit,
            attrs=attrs,
            book=book,
        )

    def render_caps(self) -> str:
        caps = self.caps
        root = ET.Element("caps")

        server = ET.SubElement(root, "server")
        server.set("title", caps.server_title)
        server.set("version", "0.1")
        if caps.server_strapline:
            server.set("strapline", caps.server_strapline)
        if caps.server_email:
            server.set("email", caps.server_email)
        if caps.server_url:
            server.set("url", caps.server_url)
        if caps.server_image:
            server.set("image", caps.server_image)

        limits = ET.SubElement(root, "limits")
        limits.set("default", str(caps.limits.default))
        limits.set("max", str(caps.limits.max))

        registration = ET.SubElement(root, "registration")
        registration.set("available", self._yn(caps.registration_available))
        registration.set("open", self._yn(caps.registration_open))

        searching = ET.SubElement(root, "searching")
        self._render_search_capability(searching, "search", caps.searching.search, caps.searching.search_params)
        self._render_search_capability(searching, "tv-search", caps.searching.tv, caps.searching.tv_params)
        self._render_search_capability(searching, "movie-search", caps.searching.movie, caps.searching.movie_params)
        self._render_search_capability(searching, "audio-search", caps.searching.audio, caps.searching.audio_params)
        self._render_search_capability(searching, "book-search", caps.searching.book, caps.searching.book_params)

        categories = ET.SubElement(root, "categories")
        for cat in caps.categories.roots:
            self._render_category(categories, cat)

        return self._tostring(root)

    def render_search(self, result: SearchResult, *, attrs: list[str] | None = None) -> str:
        rss = ET.Element("rss", {"version": "2.0"})

        channel = ET.SubElement(rss, "channel")

        if result.feed and result.feed.self_link:
            atom_link = ET.SubElement(channel, f"{{{ATOM_NS}}}link")
            atom_link.set("href", result.feed.self_link)
            atom_link.set("rel", "self")
            atom_link.set("type", "application/rss+xml")

        title = ET.SubElement(channel, "title")
        title.text = self.caps.server_title

        description = ET.SubElement(channel, "description")
        description.text = self.caps.server_title

        link = ET.SubElement(channel, "link")
        link.text = self.caps.server_url or self.base_url

        if result.feed and result.feed.language:
            language = ET.SubElement(channel, "language")
            language.text = result.feed.language

        if result.feed and result.feed.web_master:
            web_master = ET.SubElement(channel, "webMaster")
            web_master.text = result.feed.web_master

        if result.feed and result.feed.category is not None:
            channel_category = ET.SubElement(channel, "category")
            channel_category.text = result.feed.category

        if result.feed and result.feed.image:
            image_el = ET.SubElement(channel, "image")
            image_url = ET.SubElement(image_el, "url")
            image_url.text = result.feed.image.url
            image_title = ET.SubElement(image_el, "title")
            image_title.text = result.feed.image.title
            image_link = ET.SubElement(image_el, "link")
            image_link.text = result.feed.image.link
            if result.feed.image.description:
                image_desc = ET.SubElement(image_el, "description")
                image_desc.text = result.feed.image.description

        if result.api_limits:
            channel.append(self._render_api_limits(result.api_limits))

        response = ET.SubElement(channel, f"{{{NEWZNAB_NS}}}response")
        response.set("offset", str(result.offset))
        response.set("total", str(result.total))

        for element in result.extra_channel_elements:
            channel.append(self._build_extra_element(element))

        for release in result.items:
            channel.append(self._render_item(release, attrs=attrs))

        return self._tostring(rss)

    def render_error(self, code: ErrorCode, description: str | None = None) -> str:
        root = ET.Element("error")
        root.set("code", str(int(code)))
        root.set("description", description or code.name)
        return self._tostring(root)

    def _render_search_capability(self, parent: ET.Element, name: str, available: bool, supported_params: str) -> None:
        element = ET.SubElement(parent, name)
        element.set("available", self._yn(available))
        if supported_params:
            element.set("supportedParams", supported_params)

    def _render_api_limits(self, limits: APIlimits) -> ET.Element:
        element = ET.Element(f"{{{NEWZNAB_NS}}}apilimits")
        element.set("apicurrent", str(limits.apicurrent))
        element.set("apimax", str(limits.apimax))
        element.set("grabcurrent", str(limits.grabcurrent))
        element.set("grabmax", str(limits.grabmax))
        if limits.apioldesttime:
            element.set("apioldesttime", limits.apioldesttime)
        if limits.graboldesttime:
            element.set("graboldesttime", limits.graboldesttime)
        return element

    def _render_category(self, parent: ET.Element, cat) -> None:
        cat_el = ET.SubElement(parent, "category")
        cat_el.set("id", str(cat.id))
        cat_el.set("name", cat.name)
        for subcat in cat.subcats:
            sub_el = ET.SubElement(cat_el, "subcat")
            sub_el.set("id", str(subcat.id))
            sub_el.set("name", subcat.name)

    def _render_item(self, release: Release, *, attrs: list[str] | None = None) -> ET.Element:
        item = ET.Element("item")

        title = ET.SubElement(item, "title")
        title.text = release.title

        guid_text = release.details_url or release.guid
        guid = ET.SubElement(item, "guid")
        guid.set("isPermaLink", self._tf(release.guid_is_permalink))
        guid.text = guid_text

        link = release.download_url or self._getnzb_url(release.nzb_id)
        link_el = ET.SubElement(item, "link")
        link_el.text = link

        if release.comments_url:
            comments = ET.SubElement(item, "comments")
            comments.text = release.comments_url

        pub_date = ET.SubElement(item, "pubDate")
        pub_date.text = format_datetime(self._ensure_utc(release.pubdate))

        if release.category_name:
            category = ET.SubElement(item, "category")
            category.text = release.category_name

        description = ET.SubElement(item, "description")
        description.text = release.description

        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", link)
        enclosure.set("length", str(release.size))
        enclosure.set("type", "application/x-nzb")

        attr_map: dict[str, list[str]] = {
            "category": [str(release.category)],
            "size": [str(release.size)],
        }
        for key, value in release.attrs.items():
            attr_map.setdefault(key, []).append(str(value))

        requested = {name.lower() for name in attrs} if attrs else None
        for key in sorted(attr_map):
            if requested is not None and key.lower() not in requested:
                continue
            for value in attr_map[key]:
                attr = ET.SubElement(item, f"{{{NEWZNAB_NS}}}attr")
                attr.set("name", key)
                attr.set("value", value)

        for extra in release.extra_elements:
            item.append(self._build_extra_element(extra))

        return item

    def _build_extra_element(self, element: ExtraElement) -> ET.Element:
        node = ET.Element(element.tag)
        for key, value in element.attrs.items():
            node.set(key, value)
        if element.text is not None:
            node.text = element.text
        for child in element.children:
            node.append(self._build_extra_element(child))
        return node

    def _getnzb_url(self, nzb_id: str) -> str:
        params = urlencode({"id": nzb_id})
        return f"{self.base_url}/getnzb?{params}"

    def _parse_categories(self, cat_param: str | None) -> list[int]:
        if not cat_param:
            return []
        categories = []
        for part in cat_param.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                categories.append(int(part))
            except ValueError as exc:
                raise NewznabError(ErrorCode.INVALID_PARAMETER, f"Invalid category: {part}") from exc
        return categories

    def _parse_attrs(self, attrs_param: str | None) -> list[str] | None:
        if attrs_param is None:
            return None
        attrs = [part.strip() for part in attrs_param.split(",") if part.strip()]
        if not attrs:
            return []
        return attrs

    def _parse_optional_int(self, value: str | None, name: str) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise NewznabError(ErrorCode.INVALID_PARAMETER, f"Invalid {name}: {value}") from exc

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _yn(self, value: bool) -> str:
        return "yes" if value else "no"

    def _tf(self, value: bool) -> str:
        return "true" if value else "false"

    def _tostring(self, elem: ET.Element) -> str:
        return ET.tostring(elem, encoding="utf-8", xml_declaration=True).decode("utf-8")
