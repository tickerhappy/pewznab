from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

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
    TvFilters,
)


@dataclass(frozen=True)
class CatalogItem:
    release: Release
    season: int | None = None
    episode: int | None = None
    is_tv: bool = False


class Backend:
    def __init__(self) -> None:
        base_date = datetime(2026, 1, 31, tzinfo=timezone.utc)
        self.items = [
            CatalogItem(
                release=Release(
                    guid="pythonic-s01e01",
                    title="The.Pythonic.S01E01.1080p.WEB-DL-GROUP",
                    pubdate=base_date,
                    size=1_500_000_000,
                    category=5030,
                    description="The Pythonic S01E01",
                    nzb_id="pythonic-s01e01",
                ),
                season=1,
                episode=1,
                is_tv=True,
            ),
            CatalogItem(
                release=Release(
                    guid="pythonic-s01e02",
                    title="The.Pythonic.S01E02.1080p.WEB-DL-GROUP",
                    pubdate=base_date + timedelta(days=1),
                    size=1_550_000_000,
                    category=5030,
                    description="The Pythonic S01E02",
                    nzb_id="pythonic-s01e02",
                ),
                season=1,
                episode=2,
                is_tv=True,
            ),
            CatalogItem(
                release=Release(
                    guid="pythonic-s01e03",
                    title="The.Pythonic.S01E03.1080p.WEB-DL-GROUP",
                    pubdate=base_date + timedelta(days=2),
                    size=1_600_000_000,
                    category=5030,
                    description="The Pythonic S01E03",
                    nzb_id="pythonic-s01e03",
                ),
                season=1,
                episode=3,
                is_tv=True,
            ),
            CatalogItem(
                release=Release(
                    guid="pythonic-s02e01",
                    title="The.Pythonic.S02E01.1080p.WEB-DL-GROUP",
                    pubdate=base_date + timedelta(days=7),
                    size=1_700_000_000,
                    category=5030,
                    description="The Pythonic S02E01",
                    nzb_id="pythonic-s02e01",
                ),
                season=2,
                episode=1,
                is_tv=True,
            ),
            CatalogItem(
                release=Release(
                    guid="pythonic-s02e02",
                    title="The.Pythonic.S02E02.1080p.WEB-DL-GROUP",
                    pubdate=base_date + timedelta(days=8),
                    size=1_750_000_000,
                    category=5030,
                    description="The Pythonic S02E02",
                    nzb_id="pythonic-s02e02",
                ),
                season=2,
                episode=2,
                is_tv=True,
            ),
            CatalogItem(
                release=Release(
                    guid="pythonic-s02e03",
                    title="The.Pythonic.S02E03.1080p.WEB-DL-GROUP",
                    pubdate=base_date + timedelta(days=9),
                    size=1_800_000_000,
                    category=5030,
                    description="The Pythonic S02E03",
                    nzb_id="pythonic-s02e03",
                ),
                season=2,
                episode=3,
                is_tv=True,
            ),
            CatalogItem(
                release=Release(
                    guid="the-python-2026",
                    title="The.Python.2026.1080p.WEB-DL-GROUP",
                    pubdate=base_date + timedelta(days=3),
                    size=2_100_000_000,
                    category=2040,
                    description="The Python (movie)",
                    nzb_id="the-python-2026",
                ),
                is_tv=False,
            ),
        ]

    async def search(
        self,
        q: str | None,
        *,
        cats: list[int],
        maxage: int | None,
        offset: int,
        limit: int,
        tv: TvFilters | None,
    ) -> SearchResult:
        items = list(self.items)

        if cats:
            items = [item for item in items if item.release.category in cats]

        if q:
            q_lower = q.lower()
            items = [item for item in items if q_lower in item.release.title.lower()]

        if tv is not None:
            items = [item for item in items if item.is_tv]
            if tv.season is not None:
                items = [item for item in items if item.season == tv.season]
            if tv.ep is not None:
                items = [item for item in items if item.episode == tv.ep]

        if maxage is not None:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=maxage)
            items = [item for item in items if item.release.pubdate >= cutoff]

        total = len(items)
        sliced = items[offset : offset + limit]
        releases = [item.release for item in sliced]

        return SearchResult(total=total, offset=offset, limit=limit, items=releases)

    async def get_nzb(self, nzb_id: str) -> tuple[Iterable[bytes], int]:
        payload = f"<nzb id=\"{nzb_id}\"></nzb>".encode("utf-8")
        return [payload], len(payload)


app = FastAPI()
backend = Backend()

caps = Caps(
    server_title="pywznab Mock",
    limits=Limits(default=100, max=100),
    categories=CategoryTree(
        [
            Category(
                5000,
                "TV",
                [
                    Category(5030, "HD"),
                    Category(5040, "UHD"),
                ],
            ),
            Category(
                2000,
                "Movies",
                [
                    Category(2040, "HD"),
                ],
            ),
        ]
    ),
    searching=Searching(tv=True),
)

api = NewznabAPI(caps=caps, base_url="http://localhost:8000")


@app.get("/api")
async def api_endpoint(request: Request):
    try:
        req = api.parse(request.query_params)
    except NewznabError as exc:
        return Response(
            api.render_error(exc.code, exc.description),
            media_type="application/xml",
            status_code=400,
        )

    if req.type == "caps":
        return Response(api.render_caps(), media_type="application/xml")

    if req.type in ("search", "tvsearch"):
        result = await backend.search(
            req.q,
            cats=req.categories,
            maxage=req.maxage,
            offset=req.offset,
            limit=req.limit,
            tv=req.tv,
        )
        return Response(api.render_search(result), media_type="application/xml")

    return Response(
        api.render_error(ErrorCode.UNSUPPORTED_FUNCTION),
        media_type="application/xml",
        status_code=400,
    )


@app.get("/getnzb")
async def getnzb(id: str):
    chunks, size = await backend.get_nzb(id)
    return StreamingResponse(
        chunks,
        media_type="application/x-nzb",
        headers={"Content-Length": str(size)},
    )
