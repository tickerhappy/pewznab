from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Limits:
    default: int
    max: int


@dataclass(frozen=True)
class Searching:
    search: bool = True
    tv: bool = False
    movie: bool = False
    audio: bool = False
    book: bool = False
    search_params: str = "q"
    tv_params: str = "q,tvdbid,season,ep"
    movie_params: str = "q,imdbid"
    audio_params: str = "q"
    book_params: str = "q"


@dataclass
class Category:
    id: int
    name: str
    subcats: list["Category"] = field(default_factory=list)


@dataclass(frozen=True)
class CategoryTree:
    roots: Sequence[Category]

    def iter_categories(self) -> Iterable[Category]:
        for root in self.roots:
            yield root
            yield from self._iter_subcats(root)

    def _iter_subcats(self, cat: Category) -> Iterable[Category]:
        for subcat in cat.subcats:
            yield subcat
            yield from self._iter_subcats(subcat)


@dataclass(frozen=True)
class Caps:
    server_title: str
    limits: Limits
    categories: CategoryTree
    searching: Searching
    server_url: str | None = None
    server_email: str | None = None
    server_image: str | None = None
    server_strapline: str | None = None
    registration_available: bool = False
    registration_open: bool = False


@dataclass(frozen=True)
class TvFilters:
    tvdbid: str | None = None
    season: int | None = None
    ep: int | None = None


@dataclass(frozen=True)
class MovieFilters:
    imdbid: str | None = None
    genre: str | None = None


@dataclass(frozen=True)
class MusicFilters:
    artist: str | None = None
    album: str | None = None
    title: str | None = None
    label: str | None = None
    track: str | None = None
    year: int | None = None
    genre: str | None = None


@dataclass(frozen=True)
class BookFilters:
    title: str | None = None
    author: str | None = None


@dataclass(frozen=True)
class APIlimits:
    apicurrent: int
    apimax: int
    grabcurrent: int
    grabmax: int
    apioldesttime: str | None = None
    graboldesttime: str | None = None


@dataclass(frozen=True)
class FeedImage:
    url: str
    title: str
    link: str
    description: str | None = None


@dataclass(frozen=True)
class FeedMeta:
    self_link: str | None = None
    language: str | None = None
    web_master: str | None = None
    category: str | None = None
    image: FeedImage | None = None


@dataclass(frozen=True)
class ExtraElement:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    text: str | None = None
    children: Sequence["ExtraElement"] = field(default_factory=tuple)


@dataclass(frozen=True)
class Release:
    guid: str
    title: str
    pubdate: datetime
    size: int
    category: int
    description: str
    nzb_id: str
    category_name: str | None = None
    details_url: str | None = None
    comments_url: str | None = None
    download_url: str | None = None
    guid_is_permalink: bool = False
    attrs: dict[str, str] = field(default_factory=dict)
    extra_elements: Sequence[ExtraElement] = field(default_factory=tuple)


@dataclass(frozen=True)
class SearchResult:
    total: int
    offset: int
    limit: int
    items: Sequence[Release]
    feed: FeedMeta | None = None
    api_limits: APIlimits | None = None
    extra_channel_elements: Sequence[ExtraElement] = field(default_factory=tuple)
