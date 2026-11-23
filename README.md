# Cookibits

A self-hosted language model stack: a vLLM model server, an authenticating gateway in front of it, and chat front-ends that connect through the gateway.

## Layout

- `gateway/`: the authenticating proxy. See [gateway/README.md](gateway/README.md).
- `deploy/`: systemd user units and the per-host environment file template.

Machine-specific values (hostnames, addresses, keys, paths) live in gitignored files. Each one has a committed `.example` template.

## License

Apache License 2.0. See [LICENSE](LICENSE).
