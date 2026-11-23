from pathlib import Path

import httpx
import pytest
from starlette.testclient import TestClient

from cookibits_gateway import keys as keys_module
from cookibits_gateway.app import create_app
from cookibits_gateway.config import Config
from cookibits_gateway.keys import KeyStore

KEY = "ckb_test"


class Chunks(httpx.AsyncByteStream):
    """An upstream body delivered in pieces, the way vLLM streams SSE."""

    def __init__(self, *chunks: bytes):
        self._chunks = chunks

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk


def make_config(tmp_path: Path, max_body_bytes: int = 1024) -> Config:
    return Config(
        host="127.0.0.1",
        port=8480,
        upstream_url="http://engine",
        keys_file=tmp_path / "keys.toml",
        max_body_bytes=max_body_bytes,
        max_logprobs=5,
        upstream_timeout_s=10,
    )


@pytest.fixture
def seen():
    return []


@pytest.fixture
def client(tmp_path, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/health":
            return httpx.Response(200)
        return httpx.Response(
            200,
            stream=Chunks(b"data: {\"a\": 1}\n\n", b"data: [DONE]\n\n"),
            headers={"content-type": "text/event-stream"},
        )

    store = KeyStore({"tester": keys_module.hash_key(KEY)})
    app = create_app(make_config(tmp_path), keys=store, transport=httpx.MockTransport(handler))
    with TestClient(app) as c:
        yield c


def auth(**extra):
    return {"authorization": f"Bearer {KEY}", **extra}


def test_rejects_missing_key(client, seen):
    r = client.post("/v1/chat/completions", json={"messages": []})
    assert r.status_code == 401
    assert seen == []


def test_accepts_anthropic_style_key(client, seen):
    r = client.post("/v1/messages", json={"messages": []}, headers={"x-api-key": KEY})
    assert r.status_code == 200
    assert len(seen) == 1


def test_never_forwards_client_credentials(client, seen):
    client.post("/v1/chat/completions", json={"messages": []}, headers=auth(**{"x-api-key": KEY}))
    forwarded = seen[0].headers
    assert "authorization" not in forwarded
    assert "x-api-key" not in forwarded


def test_unlisted_route_is_rejected(client, seen):
    r = client.post("/invocations", json={}, headers=auth())
    assert r.status_code == 404
    assert seen == []


@pytest.mark.parametrize(
    "path,body",
    [
        ("/v1/completions", {"prompt": "x", "prompt_logprobs": 0}),
        ("/v1/chat/completions", {"messages": [], "prompt_logprobs": 1}),
        ("/v1/completions", {"prompt": "x", "echo": True, "logprobs": 1}),
        ("/v1/chat/completions", {"messages": [], "echo": True, "logprobs": True, "top_logprobs": 1}),
        ("/v1/chat/completions", {"messages": [], "echo": True, "logprobs": True}),
        ("/v1/completions", {"prompt": "x", "logprobs": 20}),
        ("/v1/chat/completions", {"messages": [], "logprobs": True, "top_logprobs": 20}),
        ("/v1/chat/completions", {"messages": [], "n": 2}),
    ],
)
def test_engine_crashing_requests_are_rejected(client, seen, path, body):
    r = client.post(path, json=body, headers=auth())
    assert r.status_code == 400
    assert seen == []


def test_small_logprobs_pass(client, seen):
    r = client.post("/v1/chat/completions", json={"messages": [], "logprobs": True, "top_logprobs": 5}, headers=auth())
    assert r.status_code == 200


def test_oversized_body_is_rejected(client, seen):
    r = client.post("/v1/chat/completions", content=b"{" + b" " * 2048 + b"}", headers=auth())
    assert r.status_code == 413
    assert seen == []


def test_invalid_json_is_rejected(client, seen):
    r = client.post("/v1/chat/completions", content=b"not json", headers=auth())
    assert r.status_code == 400


def test_health_needs_no_key(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["engine"] == "ok"


def test_engine_down_returns_502(tmp_path):
    def handler(request):
        raise httpx.ConnectError("down")

    store = KeyStore({"tester": keys_module.hash_key(KEY)})
    app = create_app(make_config(tmp_path), keys=store, transport=httpx.MockTransport(handler))
    with TestClient(app) as c:
        r = c.post("/v1/chat/completions", json={"messages": []}, headers=auth())
        assert r.status_code == 502
        assert c.get("/health").status_code == 503


def test_key_lifecycle(tmp_path):
    path = tmp_path / "keys.toml"
    key = keys_module.add(path, "mac")
    assert key.startswith("ckb_")
    assert KeyStore.load(path).identify(key) == "mac"
    assert key not in path.read_text()
    with pytest.raises(ValueError):
        keys_module.add(path, "mac")
    keys_module.revoke(path, "mac")
    assert KeyStore.load(path).identify(key) is None


def test_streams_upstream_body_unchanged(client):
    r = client.post("/v1/chat/completions", json={"messages": [], "stream": True}, headers=auth())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.content == b'data: {"a": 1}\n\ndata: [DONE]\n\n'
