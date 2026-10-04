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
are offered when reconfiguring; the checked-in initial snapshot supplies defaults
for a new configuration, and build-pin environment variables supply defaults
for keys absent from that snapshot. Nothing is downloaded or built during
configuration/checking.
The file is JSON data, not executable shell configuration. Never put secrets in
it. Use `--config /path/build.json` to select another operator-controlled file;
keep such files outside the repository/build context or explicitly ignore them.

Required reviewed values:

- Kali analyzer and Debian proxy image references ending in `@sha256:<digest>`.
- Exact OpenCode, PyGhidra MCP, Semgrep and Checkov versions. OpenCode must support the
  repository's native configuration schema; PyGhidra MCP defaults to `0.2.7`.
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

## Initial version snapshot and online resolution

The checked-in `mossback-build.json` records package releases observed on
2026-10-04 and the CodeQL **amd64** checksum. Its four unresolved fields are
`null`, not invented digests or hashes, so it intentionally fails validation
until completed. Docker registry metadata and repository HEAD APIs were not
accessible from the development session. Older cached image digests were not
substituted for current values.

On a host with Internet access, resolve all pins explicitly without building:

```sh
./scripts/build-images --config mossback-build.json --resolve-latest
./scripts/build-images --config mossback-build.json --check
./scripts/build-images --config mossback-build.json
```

Resolution uses official npm/PyPI metadata, GitHub commit/release APIs and Docker
Hub tag metadata. It selects the CodeQL checksum for the host architecture and
saves only after the entire result passes validation. API failures leave the
existing file unchanged. Resolving replaces the selected configuration with
new upstream pins and default image tags; review the diff before building.
It does not install packages, start containers or grant analyzer network access.

| Pin | Initial value | Primary source |
| --- | --- | --- |
| OpenCode | `1.18.34` | [npm latest metadata](https://registry.npmjs.org/opencode-ai/latest) |
| Semgrep | `1.179.0` | [PyPI](https://pypi.org/project/semgrep/) |
| PyGhidra MCP | `0.2.7` | [PyPI](https://pypi.org/project/pyghidra-mcp/) |
| Checkov | `3.3.20` | [upstream release](https://github.com/bridgecrewio/checkov/releases/tag/3.3.20) |
| CodeQL bundle | `2.27.1` | [release assets and archive digest](https://github.com/github/codeql-action/releases/expanded_assets/codeql-bundle-v2.27.1) |

Configuration uses the current [OpenCode schema](https://opencode.ai/config.json):
`provider`, `permission`, direct MCP entries and Markdown agent permissions.
Built-in agents are disabled and specialist tools remain role-scoped.
A real launch and permission-enforcement test are still required on the deployment
host; do not bypass permissions to make startup succeed.

APT tools such as Ghidra, TShark, binutils and Nginx are selected from the base
distribution's repositories at build time, not individually version-pinned by
this JSON. Burp JARs are operator-supplied and are not downloaded/versioned here.
Thus this snapshot does not lock every transitive or distribution package.

## Manual build commands

Export the same reviewed pins first; `.env.example` is not sourced automatically.
Then run:

```sh
podman build --build-arg BASE_IMAGE="$BASE_IMAGE" \
  --build-arg OPENCODE_VERSION="$OPENCODE_VERSION" \
  --build-arg PYGHIDRA_MCP_VERSION="${PYGHIDRA_MCP_VERSION:-0.2.7}" \
  --build-arg SEMGREP_VERSION="$SEMGREP_VERSION" \
  --build-arg CHECKOV_VERSION="$CHECKOV_VERSION" \
  --build-arg SEMGREP_RULES_COMMIT="$SEMGREP_RULES_COMMIT" \
  --build-arg WIREMCP_COMMIT="$WIREMCP_COMMIT" \
  --build-arg CODEQL_BUNDLE_TAG="$CODEQL_BUNDLE_TAG" \
  --build-arg CODEQL_BUNDLE_SHA256="$CODEQL_BUNDLE_SHA256" \
  -t mossback:local .
podman build -f Containerfile.proxy \
  --build-arg PROXY_BASE_IMAGE="$PROXY_BASE_IMAGE" -t mossback-proxy:local .
```
