# cookibits-gateway

Authenticating proxy in front of a local vLLM server. Clients reach the model only through it.

## What it does

- Requires a per-client API key, sent as `Authorization: Bearer <key>` (OpenAI clients) or `x-api-key: <key>` (Anthropic clients). Keys are never forwarded to vLLM.
- Forwards only these routes: `POST /v1/messages`, `POST /v1/messages/count_tokens`, `POST /v1/chat/completions`, `POST /v1/completions`, `GET /v1/models`. `GET /health` needs no key.
- Rejects request shapes that crash or overload the engine: `prompt_logprobs` (any value), `echo` combined with logprobs, logprobs above the configured cap, and `n` other than 1.
- Caps the request body size.
- Streams responses back unchanged, including server-sent events.
- Logs one JSON line per request: client name, method, path, status and duration. Request and response content is never logged.

## Install

```sh
python3 -m venv /path/to/gateway-venv
/path/to/gateway-venv/bin/pip install ./gateway
cp gateway/config.example.toml /path/to/config.toml   # then edit
export COOKIBITS_GATEWAY_CONFIG=/path/to/config.toml
```

## Keys

```sh
cookibits-gateway keys add open-webui    # prints the key once
cookibits-gateway keys list
cookibits-gateway keys revoke open-webui
```

Only a SHA-256 hash of each key is stored. Restart the gateway after adding or revoking a key.

## Run

```sh
cookibits-gateway serve
```

For a long-running service, use `deploy/systemd/cookibits-gateway.service`.

## Test

```sh
pip install './gateway[test]'
pytest gateway
```
