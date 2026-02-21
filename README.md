# pywznab


Minimal Python library for implementing a Newznab-compatible API.

This library provides request parsing and response generation. You provide the web server and backend (e.g. search, storage, database).


_(pywznab is pronounced “pews-nab”)_

## Installation

Install into your active virtual environment:

```bash
uv pip install /path/to/pywznab
```

If you are developing pywznab itself you can use:
```bash
uv pip install -e /path/to/pywznab
```
-e links the source directory directly, so code changes are picked up instantly.

_(Regular `pip` also works)_

------------------------------------------------------------------------

## Minimal Integration Example

``` python
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from pywznab import (
    NewznabAPI,
    NewznabError,
    ErrorCode,
    Caps,
    Limits,
    Searching,
    Category,
    CategoryTree,
    CapsRequest,
    SearchRequest,
    TvSearchRequest,
    MovieRequest,
    MusicRequest,
    BookRequest,
)

app = FastAPI()

caps = Caps(
    server_title="my indexer",
    limits=Limits(default=100, max=200),
    categories=CategoryTree([
        Category(5000, "TV", [Category(5030, "HD")])
    ]),
    searching=Searching(tv=True, movie=True, audio=True, book=True),
)

api = NewznabAPI(caps=caps, base_url="http://localhost:8000")


@app.get("/api")
async def api_route(request: Request):
    try:
        req = api.parse(request.query_params)
    except NewznabError as exc:
        return Response(
            api.render_error(exc.code, exc.description),
            media_type="application/xml",
            status_code=400,
        )

    if isinstance(req, CapsRequest):
        return Response(api.render_caps(), media_type="application/xml")

    if isinstance(req, (SearchRequest, TvSearchRequest, MovieRequest, MusicRequest, BookRequest)):
        # Build and return a SearchResult from your backend here.
        # Example:
        # result = backend.search(req)
        result = ...
        return Response(
            api.render_search(result, attrs=req.attrs),
            media_type="application/xml",
        )

    return Response(
        api.render_error(ErrorCode.UNSUPPORTED_FUNCTION),
        media_type="application/xml",
        status_code=400,
    )


@app.get("/getnzb")
async def getnzb(id: str):
    # Example 1: in-memory NZB payload
    payload = b"<nzb>...</nzb>"
    return StreamingResponse(
        [payload],
        media_type="application/x-nzb",
        headers={"Content-Length": str(len(payload))},
    )

    # Example 2: streaming a local file
    # from pathlib import Path
    #
    # path = Path("/data/nzbs/item.nzb")
    # size = path.stat().st_size
    #
    # def chunks():
    #     with path.open("rb") as f:
    #         while True:
    #             block = f.read(1024 * 64)
    #             if not block:
    #                 break
    #             yield block
    #
    # return StreamingResponse(
    #     chunks(),
    #     media_type="application/x-nzb",
    #     headers={"Content-Length": str(size)},
    # )
```

`result = ...` is a placeholder. Replace it with a `SearchResult`
instance produced by your backend.

### Example project

There's a runnable example in `examples/mock_app.py`.

```bash
uv pip install fastapi uvicorn
uv run uvicorn examples.mock_app:app --reload --port 8000
```



------------------------------------------------------------------------

## Public API

### Core

-   `NewznabAPI`

### Requests

-   `CapsRequest`
-   `SearchRequest`
-   `TvSearchRequest`
-   `MovieRequest`
-   `MusicRequest`
-   `BookRequest`

### Models

-   `Caps`, `Limits`, `Searching`
-   `Category`, `CategoryTree`
-   `TvFilters`, `MovieFilters`, `MusicFilters`, `BookFilters`
-   `Release`, `SearchResult`
-   `FeedMeta`, `FeedImage`, `APIlimits`
-   `ExtraElement`

### Errors

-   `NewznabError`
-   `ErrorCode`

------------------------------------------------------------------------

## Parsing

`NewznabAPI.parse(params)` returns one of the request types above.

Common search fields:

-   `q: str | None`
-   `categories: list[int]`
-   `maxage: int | None`
-   `offset: int`
-   `limit: int` (clamped to `Caps.limits.max`)
-   `attrs: list[str] | None`

Endpoint-specific filters:

-   `req.tv`
-   `req.movie`
-   `req.music`
-   `req.book`

Validation raises `NewznabError` with:

-   `MISSING_PARAMETER`
-   `UNSUPPORTED_FUNCTION`
-   `INVALID_PARAMETER`

------------------------------------------------------------------------

## Rendering

### `render_caps()`

Renders:

-   `<server>`
-   `<limits>`
-   `<registration>`
-   `<searching>`
-   `<categories>`

### `render_search(result, attrs=None)`

Renders RSS 2.0 with:

-   Required channel fields
-   Optional `FeedMeta`
-   `newznab:response` (offset/total)
-   Optional `newznab:apilimits`

Each `Release` renders:

-   `title`, `guid`, `link`, `pubDate`
-   `description`
-   `enclosure` (`application/x-nzb`)
-   `newznab:attr`:
    -   always `category`, `size`
    -   plus `Release.attrs`

If `attrs` is provided, output is filtered to those attribute names.

### `render_error(code, description=None)`

``` xml
<error code="..." description="..."/>
```

------------------------------------------------------------------------

## XML Extension Hooks

Inject custom XML via `ExtraElement`.

-   `SearchResult.extra_channel_elements`
-   `Release.extra_elements`

`ExtraElement`:

-   `tag`
-   `attrs`
-   `text`
-   `children`

------------------------------------------------------------------------

## Layout

-   `api.py` -- parsing + rendering
-   `models.py` -- data models
-   `errors.py` -- typed errors
