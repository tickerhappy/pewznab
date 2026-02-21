from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Mapping
from urllib.parse import urlencode, urljoin
import xml.etree.ElementTree as ET

from .errors import ErrorCode, NewznabError
from .models import Caps, Release, SearchResult, TvFilters


NEWZNAB_NS = "http://www.newznab.com/DTD/2008/feeds/attributes/"

ET.register_namespace("newznab", NEWZNAB_NS)


@dataclass(frozen=True)
class ParsedRequest:
    type: str
    q: str | None
    categories: list[int]
    maxage: int | None
    offset: int
    limit: int
    tv: TvFilters | None


class NewznabAPI:
    def __init__(self, *, caps: Caps, base_url: str):
        self.caps = caps
        self.base_url = base_url.rstrip("/")

    def parse(self, params: Mapping[str, str]) -> ParsedRequest:
        request_type = params.get("t")
        if not request_type:
            raise NewznabError(ErrorCode.MISSING_PARAMETER, "Missing parameter: t")

        if request_type not in {"caps", "search", "tvsearch"}:
            raise NewznabError(ErrorCode.UNSUPPORTED_FUNCTION, f"Unsupported function: {request_type}")

        if request_type == "caps":
            return ParsedRequest(
                type="caps",
                q=None,
                categories=[],
                maxage=None,
                offset=0,
                limit=0,
                tv=None,
            )

        q = params.get("q") or None
        categories = self._parse_categories(params.get("cat"))
        maxage = self._parse_optional_int(params.get("maxage"), "maxage")
        offset = self._parse_optional_int(params.get("offset"), "offset") or 0
        limit = self._parse_optional_int(params.get("limit"), "limit") or self.caps.limits.default

        if offset < 0:
            raise NewznabError(ErrorCode.INVALID_PARAMETER, "Invalid offset")
        if limit < 0:
            raise NewznabError(ErrorCode.INVALID_PARAMETER, "Invalid limit")

        if limit > self.caps.limits.max:
            limit = self.caps.limits.max

        tv_filters = None
        if request_type == "tvsearch":
            tv_filters = TvFilters(
                tvdbid=params.get("tvdbid") or None,
                season=self._parse_optional_int(params.get("season"), "season"),
                ep=self._parse_optional_int(params.get("ep"), "ep"),
            )

        return ParsedRequest(
            type=request_type,
            q=q,
            categories=categories,
            maxage=maxage,
            offset=offset,
            limit=limit,
            tv=tv_filters,
        )

    def render_caps(self) -> str:
        caps = self.caps
        root = ET.Element("caps")

        server = ET.SubElement(root, "server")
        server.set("title", caps.server_title)
        server.set("version", "0.1")

        limits = ET.SubElement(root, "limits")
        limits.set("default", str(caps.limits.default))
        limits.set("max", str(caps.limits.max))

        registration = ET.SubElement(root, "registration")
        registration.set("available", "no")
        registration.set("open", "no")

        searching = ET.SubElement(root, "searching")
        search = ET.SubElement(searching, "search")
        search.set("available", "yes" if caps.searching.search else "no")
        search.set("supportedParams", "q")

        tv_search = ET.SubElement(searching, "tv-search")
        tv_search.set("available", "yes" if caps.searching.tv else "no")
        tv_search.set("supportedParams", "q,tvdbid,season,ep")

        categories = ET.SubElement(root, "categories")
        for cat in caps.categories.roots:
            self._render_category(categories, cat)

        return self._tostring(root)

    def render_search(self, result: SearchResult) -> str:
        rss = ET.Element("rss", {"version": "2.0"})

        channel = ET.SubElement(rss, "channel")
        title = ET.SubElement(channel, "title")
        title.text = self.caps.server_title

        link = ET.SubElement(channel, "link")
        link.text = self.base_url

        description = ET.SubElement(channel, "description")
        description.text = self.caps.server_title

        response = ET.SubElement(channel, f"{{{NEWZNAB_NS}}}response")
        response.set("offset", str(result.offset))
        response.set("total", str(result.total))

        for release in result.items:
            channel.append(self._render_item(release))

        return self._tostring(rss)

    def render_error(self, code: ErrorCode, description: str | None = None) -> str:
        root = ET.Element("error")
        root.set("code", str(int(code)))
        root.set("description", description or code.name)
        return self._tostring(root)

    def _render_category(self, parent: ET.Element, cat) -> None:
        cat_el = ET.SubElement(parent, "category")
        cat_el.set("id", str(cat.id))
        cat_el.set("name", cat.name)
        for subcat in cat.subcats:
            sub_el = ET.SubElement(cat_el, "subcat")
            sub_el.set("id", str(subcat.id))
            sub_el.set("name", subcat.name)

    def _render_item(self, release: Release) -> ET.Element:
        item = ET.Element("item")

        title = ET.SubElement(item, "title")
        title.text = release.title

        guid = ET.SubElement(item, "guid")
        guid.set("isPermaLink", "false")
        guid.text = release.guid

        pub_date = ET.SubElement(item, "pubDate")
        pub_date.text = format_datetime(self._ensure_utc(release.pubdate))

        description = ET.SubElement(item, "description")
        description.text = release.description

        link = self._getnzb_url(release.nzb_id)
        link_el = ET.SubElement(item, "link")
        link_el.text = link

        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", link)
        enclosure.set("length", str(release.size))
        enclosure.set("type", "application/x-nzb")

        size_attr = ET.SubElement(item, f"{{{NEWZNAB_NS}}}attr")
        size_attr.set("name", "size")
        size_attr.set("value", str(release.size))

        cat_attr = ET.SubElement(item, f"{{{NEWZNAB_NS}}}attr")
        cat_attr.set("name", "category")
        cat_attr.set("value", str(release.category))

        return item

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

    def _tostring(self, elem: ET.Element) -> str:
        return ET.tostring(elem, encoding="utf-8", xml_declaration=True).decode("utf-8")
