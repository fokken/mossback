# Building mossback

Install rootless Podman and Python 3 on the host. Build-time downloads require
Internet access; the running analyzer remains restricted to its LLM proxy.
Run without sudo from a normal host terminal.

```sh
./scripts/build-images --configure
./scripts/build-images --check
./scripts/build-images
```

Configuration prompts collect required build inputs and save a reusable,
Git-ignored `.mossback-build.json` with restrictive permissions. Existing values
are offered when reconfiguring; build-pin environment variables can supply
initial defaults. Nothing is downloaded or built during configuration/checking.
The file is JSON data, not executable shell configuration. Never put secrets in
it. Use `--config /path/build.json` to select another operator-controlled file;
keep such files outside the repository/build context or explicitly ignore them.

Required reviewed values:

- Kali analyzer and Debian proxy image references ending in `@sha256:<digest>`.
- Exact OpenCode, PyGhidra MCP and Semgrep versions. OpenCode must support the
  repository's V2 configuration; PyGhidra MCP defaults to `0.2.7`.
- Full 40-character Semgrep rules and WireMCP source commits.
- CodeQL bundle tag and trusted archive SHA256 matching your host architecture:
  `linux64` for amd64, `linux-arm64` for arm64. See [source tools](source-tools.md).

The helper rejects missing pins, floating refs, malformed digests and unknown
settings before invoking Podman. Validation checks syntax, not upstream
existence, trust or compatibility; no versions are silently selected as latest.
It verifies rootless execution, builds the proxy then the analyzer, and stops
on errors. Successful earlier images remain if a later build fails. Default
tags are `mossback-proxy:local` and `mossback:local`; custom tags must also be
exported as `PROXY_IMAGE` and `ANALYZER_IMAGE` when launching.

`.containerignore` excludes default assessment directories, credentials, local
build settings and Git metadata from the build context. Put assessment data
outside the repository if using other directory names. Package dependencies
are not fully locked; reviewed inputs do not guarantee byte-identical rebuilds.

After building, configure `LLM_HOST`, `LLM_PORT` and `LLM_MODEL`, then run:

```sh
./scripts/run-analysis --check-isolation ./artifacts ./analysis-output
./scripts/run-analysis ./artifacts ./analysis-output
```

Image builds and runtime integration require verification on your deployment
host. The local unit tests do not substitute for these checks.

## Manual build alternative

Export the same reviewed pins first; `.env.example` is not sourced automatically.
Then run:

```sh
podman build --build-arg BASE_IMAGE="$BASE_IMAGE" \
  --build-arg OPENCODE_VERSION="$OPENCODE_VERSION" \
  --build-arg PYGHIDRA_MCP_VERSION="${PYGHIDRA_MCP_VERSION:-0.2.7}" \
  --build-arg SEMGREP_VERSION="$SEMGREP_VERSION" \
  --build-arg SEMGREP_RULES_COMMIT="$SEMGREP_RULES_COMMIT" \
  --build-arg WIREMCP_COMMIT="$WIREMCP_COMMIT" \
  --build-arg CODEQL_BUNDLE_TAG="$CODEQL_BUNDLE_TAG" \
  --build-arg CODEQL_BUNDLE_SHA256="$CODEQL_BUNDLE_SHA256" \
  -t mossback:local .
podman build -f Containerfile.proxy \
  --build-arg PROXY_BASE_IMAGE="$PROXY_BASE_IMAGE" -t mossback-proxy:local .
```
