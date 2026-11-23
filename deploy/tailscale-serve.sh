#!/bin/sh
# Publish the gateway and Open WebUI on the tailnet over HTTPS.
# Both services listen on 127.0.0.1 only; Tailscale terminates TLS with the
# machine's ts.net certificate. Requires `tailscale set --operator=<user>`
# once, and HTTPS certificates enabled for the tailnet.
set -eu

GATEWAY_PORT="${COOKIBITS_GATEWAY_PORT:-8480}"
WEBUI_PORT="${COOKIBITS_WEBUI_PORT:-8481}"

tailscale serve --bg --https="$GATEWAY_PORT" "http://127.0.0.1:$GATEWAY_PORT"
tailscale serve --bg --https="$WEBUI_PORT" "http://127.0.0.1:$WEBUI_PORT"
tailscale serve status
