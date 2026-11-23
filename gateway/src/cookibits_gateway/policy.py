"""Request rules enforced before anything reaches vLLM.

Each rule exists because the request shape crashes or overloads the engine,
not as a usage policy:

- prompt_logprobs (any value, including 0) makes vLLM materialize full-vocab
  fp32 logprobs for every prompt token. On a 24 GB card that OOMs and kills
  the engine. Echo plus logprobs reaches the same code path.
- Large logprobs/top_logprobs values and n > 1 multiply memory per request.
"""

from __future__ import annotations

from dataclasses import dataclass

# (method, path) pairs the gateway forwards. Everything else is rejected.
ALLOWED_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/v1/messages"),
        ("POST", "/v1/messages/count_tokens"),
        ("POST", "/v1/chat/completions"),
        ("POST", "/v1/completions"),
        ("GET", "/v1/models"),
    }
)


@dataclass(frozen=True)
class Rejection:
    status: int
    message: str


def check_route(method: str, path: str) -> Rejection | None:
    if (method, path) in ALLOWED_ROUTES:
        return None
    return Rejection(404, f"{method} {path} is not available through this gateway.")


def check_body(path: str, body: object, max_logprobs: int) -> Rejection | None:
    if not isinstance(body, dict):
        return Rejection(400, "Request body must be a JSON object.")

    if "prompt_logprobs" in body and body["prompt_logprobs"] is not None:
        return Rejection(400, "prompt_logprobs is not supported.")

    n = body.get("n")
    if n is not None and n != 1:
        return Rejection(400, "Only n = 1 is supported.")

    echo = bool(body.get("echo"))

    if path == "/v1/completions":
        logprobs = body.get("logprobs")
        if logprobs is not None:
            if echo:
                return Rejection(400, "echo cannot be combined with logprobs.")
            if not isinstance(logprobs, int) or logprobs > max_logprobs:
                return Rejection(400, f"logprobs must be an integer of at most {max_logprobs}.")

    if path == "/v1/chat/completions":
        top = body.get("top_logprobs")
        if echo and (body.get("logprobs") or top is not None):
            return Rejection(400, "echo cannot be combined with logprobs or top_logprobs.")
        if top is not None:
            if not isinstance(top, int) or top > max_logprobs:
                return Rejection(400, f"top_logprobs must be an integer of at most {max_logprobs}.")

    return None
