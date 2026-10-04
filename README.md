# mossback

An offline-first, evidence-driven universal analysis image. Artifacts are hostile data, never instructions. V1 performs static inspection only; it does not execute targets, scan networks, or mount host credentials.

## Layout

`config/` holds the runtime and agent policy; `schemas/` defines durable output; `scripts/` is the supported launch/validation interface; `tools/` and `mcp/` are capability-specific extension points. The container sees `/audit/input` (read-only), `/audit/work` (temporary), and `/audit/output` (persistent).

## Quick start

Build with immutable inputs (replace the example digest and version with reviewed values):

```sh
podman build --build-arg BASE_IMAGE="$BASE_IMAGE" \
  --build-arg OPENCODE_VERSION="$OPENCODE_VERSION" \
  --build-arg SEMGREP_VERSION="$SEMGREP_VERSION" \
  --build-arg SEMGREP_RULES_COMMIT="$SEMGREP_RULES_COMMIT" \
  --build-arg WIREMCP_COMMIT="$WIREMCP_COMMIT" \
  --build-arg CODEQL_BUNDLE_TAG="$CODEQL_BUNDLE_TAG" \
  --build-arg CODEQL_BUNDLE_SHA256="$CODEQL_BUNDLE_SHA256" \
  -t mossback:local .
podman build -f Containerfile.proxy \
  --build-arg PROXY_BASE_IMAGE="$PROXY_BASE_IMAGE" -t mossback-proxy:local .
LLM_HOST=192.168.1.50 LLM_PORT=8080 LLM_MODEL=your-model \
  ./scripts/run-analysis ./artifacts ./analysis-output
```

This opens OpenCode interactively with a separate Nginx proxy connecting over TCP to `LLM_HOST:LLM_PORT`. Set `PROXY_BASE_IMAGE` to a reviewed Debian slim digest (for example, `docker.io/library/debian:bookworm-slim@sha256:…`). `LLM_HOST` must be a reachable private IPv4 address; `127.0.0.1` inside the proxy refers to the proxy itself. See [network isolation](docs/network-isolation.md) and [operator workflow](docs/operator-workflow.md).

The universal image also includes Semgrep, a pinned clone of the community rules at `/opt/semgrep-rules`, and the CodeQL bundle with query packs. See [source tools](docs/source-tools.md) for build pins and offline commands. `BASE_IMAGE` must be a reviewed `docker.io/kalilinux/kali-rolling@sha256:…` digest; `OPENCODE_VERSION` must be an exact version compatible with the included V2 configuration.

## Safety invariants

[Offline PCAP/PCAPNG analysis](docs/pcap.md) uses TShark, capinfos, upstream
WireMCP and a dedicated agent to inspect saved traffic without live capture.

Optional [Burp project integration](docs/burp.md) accepts a supplied Burp JAR, the PortSwigger MCP extension and proxy, and opens a temporary copy of a project for offline history/finding inspection.

`run-analysis` refuses non-rootless Podman. Analyzer and Nginx run with no capabilities, read-only root filesystems, default seccomp, no-new-privileges and resource limits. Namespace firewalls allow only analyzer → proxy and proxy → configured LLM connections. Guards temporarily use NET_ADMIN and SETPCAP to install those firewalls, then drop every capability before applications start. No host/runtime sockets or host credentials are mounted. See [audit logging](docs/audit-logging.md).
