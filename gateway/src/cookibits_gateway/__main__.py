"""Command line: run the gateway, or manage client keys.

    cookibits-gateway serve
    cookibits-gateway keys add <name>
    cookibits-gateway keys list
    cookibits-gateway keys revoke <name>

The config file path comes from COOKIBITS_GATEWAY_CONFIG.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import config as config_module
from . import keys as keys_module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cookibits-gateway")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="run the gateway")

    keys_parser = sub.add_parser("keys", help="manage client keys")
    keys_sub = keys_parser.add_subparsers(dest="action", required=True)
    keys_sub.add_parser("list")
    for action in ("add", "revoke"):
        p = keys_sub.add_parser(action)
        p.add_argument("name")

    args = parser.parse_args(argv)
    cfg = config_module.load()

    if args.command == "serve":
        import uvicorn

        from .app import create_app

        logging.basicConfig(level=logging.INFO, format="%(message)s")
        uvicorn.run(create_app(cfg), host=cfg.host, port=cfg.port, access_log=False)
        return 0

    try:
        if args.action == "list":
            for name in keys_module.KeyStore.load(cfg.keys_file).names():
                print(name)
        elif args.action == "add":
            key = keys_module.add(cfg.keys_file, args.name)
            print(key)
            print("Store this key now. It cannot be shown again.", file=sys.stderr)
        elif args.action == "revoke":
            keys_module.revoke(cfg.keys_file, args.name)
            print(f"Revoked {args.name}. Restart the gateway to apply.", file=sys.stderr)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
