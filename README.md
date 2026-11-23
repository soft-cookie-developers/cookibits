# Cookibits

A self-hosted language model stack: a vLLM model server, an authenticating gateway in front of it, and chat front-ends that connect through the gateway.

## Layout

- `gateway/`: the authenticating proxy. See [gateway/README.md](gateway/README.md).
- `deploy/systemd/`: user units for the model server and the gateway.
- `deploy/webui/`: Open WebUI as a gateway client, run with Docker Compose.
- `deploy/tailscale-serve.sh`: publishes the gateway and Open WebUI on a tailnet over HTTPS.

Machine-specific values (hostnames, addresses, keys, paths) live in gitignored files. Each one has a committed `.example` template.

## License

Apache License 2.0. See [LICENSE](LICENSE).
