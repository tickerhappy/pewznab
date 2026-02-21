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


@dataclass(frozen=True)
class TvFilters:
    tvdbid: str | None = None
    season: int | None = None
    ep: int | None = None


@dataclass(frozen=True)
class Release:
    guid: str
    title: str
    pubdate: datetime
    size: int
    category: int
    description: str
    nzb_id: str


@dataclass(frozen=True)
class SearchResult:
    total: int
    offset: int
    limit: int
    items: Sequence[Release]
