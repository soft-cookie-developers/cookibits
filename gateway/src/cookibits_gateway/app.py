"""The gateway application: authenticate, check, forward, stream back."""

from __future__ import annotations

import contextlib
import json
import logging
import time

import httpx
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from . import policy
from .config import Config
from .keys import KeyStore

log = logging.getLogger("cookibits.gateway")

# Request headers passed through to vLLM. Credentials are never forwarded.
FORWARD_REQUEST_HEADERS = ("content-type", "accept", "anthropic-version", "anthropic-beta")
# Response headers passed back to the client.
FORWARD_RESPONSE_HEADERS = ("content-type", "cache-control")


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": {"message": message}}, status_code=status)


def _client_key(request: Request) -> str | None:
    """Accept OpenAI-style bearer tokens and Anthropic-style x-api-key."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key")


async def _read_body(request: Request, limit: int) -> bytes | None:
    """Read the body, or return None once it exceeds the limit."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        return None
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _log(client: str | None, request: Request, status: int, started: float, note: str = "") -> None:
    record = {
        "client": client,
        "method": request.method,
        "path": request.url.path,
        "status": status,
        "ms": round((time.monotonic() - started) * 1000),
    }
    if note:
        record["note"] = note
    log.info(json.dumps(record))


def create_app(config: Config, keys: KeyStore | None = None, transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    keys = keys if keys is not None else KeyStore.load(config.keys_file)
    upstream = httpx.AsyncClient(
        base_url=config.upstream_url,
        timeout=httpx.Timeout(config.upstream_timeout_s, connect=5.0),
        transport=transport,
    )

    async def health(request: Request) -> Response:
        try:
            r = await upstream.get("/health", timeout=5.0)
            ok = r.status_code == 200
        except httpx.HTTPError:
            ok = False
        return JSONResponse({"gateway": "ok", "engine": "ok" if ok else "unavailable"}, status_code=200 if ok else 503)

    async def proxy(request: Request) -> Response:
        started = time.monotonic()
        path = request.url.path

        key = _client_key(request)
        client = keys.identify(key) if key else None
        if client is None:
            _log(None, request, 401, started)
            return _error(401, "Missing or invalid API key.")

        rejection = policy.check_route(request.method, path)
        if rejection:
            _log(client, request, rejection.status, started)
            return _error(rejection.status, rejection.message)

        body = b""
        if request.method == "POST":
            raw = await _read_body(request, config.max_body_bytes)
            if raw is None:
                _log(client, request, 413, started)
                return _error(413, f"Request body exceeds {config.max_body_bytes} bytes.")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                _log(client, request, 400, started)
                return _error(400, "Request body is not valid JSON.")
            rejection = policy.check_body(path, parsed, config.max_logprobs)
            if rejection:
                _log(client, request, rejection.status, started, rejection.message)
                return _error(rejection.status, rejection.message)
            body = raw

        headers = {h: request.headers[h] for h in FORWARD_REQUEST_HEADERS if h in request.headers}
        upstream_request = upstream.build_request(
            request.method, path, params=request.query_params, headers=headers, content=body
        )
        try:
            upstream_response = await upstream.send(upstream_request, stream=True)
        except httpx.HTTPError:
            _log(client, request, 502, started)
            return _error(502, "The model server is unavailable.")

        response_headers = {
            h: upstream_response.headers[h] for h in FORWARD_RESPONSE_HEADERS if h in upstream_response.headers
        }

        async def finish() -> None:
            await upstream_response.aclose()
            _log(client, request, upstream_response.status_code, started)

        return StreamingResponse(
            upstream_response.aiter_raw(),
            status_code=upstream_response.status_code,
            headers=response_headers,
            background=BackgroundTask(finish),
        )

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/{path:path}", proxy, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
    ]

    @contextlib.asynccontextmanager
    async def lifespan(app):
        yield
        await upstream.aclose()

    return Starlette(routes=routes, lifespan=lifespan)
