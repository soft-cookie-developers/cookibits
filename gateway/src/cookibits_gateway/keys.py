"""Per-client API keys.

Only a SHA-256 hash of each key is stored. A key is shown once, when it is
created, and cannot be recovered afterwards.

keys.toml layout:

    [clients.open-webui]
    sha256 = "<hex digest>"
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import tomllib
from pathlib import Path

KEY_PREFIX = "ckb_"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class KeyStore:
    def __init__(self, digests: dict[str, str]):
        self._digests = digests

    @classmethod
    def load(cls, path: Path) -> "KeyStore":
        if not path.exists():
            return cls({})
        with path.open("rb") as f:
            raw = tomllib.load(f)
        clients = raw.get("clients", {})
        return cls({name: entry["sha256"] for name, entry in clients.items()})

    def identify(self, key: str) -> str | None:
        """Return the client name for a key, or None if it is not valid."""
        digest = hash_key(key)
        match = None
        # Compare against every entry so timing does not reveal which matched.
        for name, stored in self._digests.items():
            if hmac.compare_digest(digest, stored):
                match = name
        return match

    def names(self) -> list[str]:
        return sorted(self._digests)


def _write(path: Path, digests: dict[str, str]) -> None:
    lines = []
    for name in sorted(digests):
        lines.append(f'[clients."{name}"]')
        lines.append(f'sha256 = "{digests[name]}"')
        lines.append("")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines))
    tmp.chmod(0o600)
    tmp.replace(path)


def add(path: Path, name: str) -> str:
    store = KeyStore.load(path)
    digests = dict(store._digests)
    if name in digests:
        raise ValueError(f"A key named {name!r} already exists. Revoke it first.")
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    digests[name] = hash_key(key)
    _write(path, digests)
    return key


def revoke(path: Path, name: str) -> None:
    store = KeyStore.load(path)
    digests = dict(store._digests)
    if name not in digests:
        raise ValueError(f"No key named {name!r}.")
    del digests[name]
    _write(path, digests)
