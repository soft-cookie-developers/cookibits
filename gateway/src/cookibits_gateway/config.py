"""Gateway configuration, loaded from a per-host TOML file.

The real file (config.toml) is gitignored because it holds machine-specific
values. config.example.toml documents every field.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_ENV = "COOKIBITS_GATEWAY_CONFIG"


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    upstream_url: str
    keys_file: Path
    max_body_bytes: int
    max_logprobs: int
    upstream_timeout_s: float


def load(path: Path | None = None) -> Config:
    if path is None:
        env = os.environ.get(CONFIG_ENV)
        if not env:
            raise SystemExit(f"Set {CONFIG_ENV} to the gateway config file path.")
        path = Path(env)
    with path.open("rb") as f:
        raw = tomllib.load(f)

    server = raw.get("server", {})
    upstream = raw.get("upstream", {})
    limits = raw.get("limits", {})
    keys = raw.get("keys", {})

    keys_file = Path(keys.get("file", "keys.toml"))
    if not keys_file.is_absolute():
        keys_file = path.parent / keys_file

    return Config(
        host=server.get("host", "127.0.0.1"),
        port=int(server.get("port", 8480)),
        upstream_url=upstream.get("url", "http://127.0.0.1:8000").rstrip("/"),
        keys_file=keys_file,
        max_body_bytes=int(limits.get("max_body_bytes", 4 * 1024 * 1024)),
        max_logprobs=int(limits.get("max_logprobs", 5)),
        upstream_timeout_s=float(upstream.get("timeout_s", 600)),
    )
