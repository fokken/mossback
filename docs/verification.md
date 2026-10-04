# Verification gaps and deployment checklist

Review date: 2026-10-04. This repository is a bootstrap, not a fully validated
deployment. Host-only tests use mocked Podman calls for launcher behavior;
they do not prove container, firewall or agent-runtime enforcement.

## Known gaps

- **Output validation is permissive.** `scripts/validate-output` passes a
  nonexistent directory or absent `findings.jsonl`/`run.json`. It checks only
  selected fields in existing files, not the full schemas, evidence existence,
  duplicate IDs, module JSON, report, notebooks or preservation manifests. Some malformed
  JSON value types can cause an exception rather than a validation diagnostic.
- **Assessment metadata is incomplete.** The launcher writes an operator
  lifecycle record outside output; the entrypoint writes `run-context.json`.
  Neither creates schema-compatible assessment `output/run.json`, input hashes
  or a complete tool-version inventory. Reporter instructions currently cover
  findings and the report, not creation of this assessment metadata.
- **Burp runtime/output overlap is not rejected.** Keep trusted Burp software
  outside input, output, rules and audit trees. The launcher checks all of these
  except output. Overlap can expose trusted JARs through writable output despite
  the read-only runtime mount. A launcher guard and regression test are needed.
- **Role policies are not immutable OS boundaries.** All agents and MCPs share
  writable work/output. Global config and workspace policy are denied native
  edits, but new project config or `.opencode` files beneath work are not.
  OpenCode can merge project configuration and discover plugins/agents.
  Avoid starting it in artifact directories or importing their configuration.
  Stronger trusted-config enforcement needs design and pinned-runtime testing;
  the namespace firewall remains independent of these agent permissions.
- **Offline OpenCode startup needs verification.** Autoupdate and sharing are
  disabled in JSON, but models fetching, default plugins and automatic LSP
  downloads are not explicitly disabled by this entrypoint. The pinned runtime
  also schedules configuration-directory dependency installation. Verify a
  fresh-cache launch; preload required dependencies at build time rather than
  relaxing egress. Both configured provider SDKs are bundled in the pinned
  OpenCode source, so those SDKs alone do not require runtime installation.
- **Build resolution is not a compatibility test.** The initial snapshot has
  four unresolved pins and an amd64 CodeQL checksum. `--resolve-latest` refreshes
  all upstream pins for the host architecture and resets image tags to defaults.
  Transitive Python/npm and APT dependencies remain unlocked. External API
  failures leave the selected file unchanged; current upstream lookups must be
  tested on a connected host.

OpenCode references: [configuration precedence](https://opencode.ai/docs/config/),
[offline-related flags](https://opencode.ai/docs/cli/#environment-variables),
[pinned dependency setup](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/config/config.ts)
and [bundled providers](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/opencode/src/provider/provider.ts).

## Checks before deployment

1. Run `./tests/bootstrap.sh`; review pins and build both images on the intended
   architecture using rootless Podman. Retain the reviewed configuration.
2. Confirm mount trees are disjoint and permissions/SELinux labels work without
   mounting host credentials or using privileged mode.
3. Run `--check-isolation`. Separately verify proxy egress denies other private,
   public and metadata destinations, including IPv6 and DNS. The current smoke
   test probes analyzer egress and proxy routes, not proxy egress itself.
4. Test a fresh interactive session against the intended LLM: tool calls,
   streaming, model limits, HTTPS identity and credential/log separation.
5. Test actual role permissions, configuration discovery and MCP tool names
   with the pinned OpenCode release. Use trusted fixture binaries/captures and
   source-tool smoke tests; verify Checkov scanning separately. Burp additionally
   needs edition/license, JDK, extension settings and headless-startup checks.
6. Inspect persisted evidence, findings, report, manifests and metadata directly;
   confirm cleanup and review audit logs. Do not equate a zero exit code with
   complete analysis or confirmed vulnerabilities.

The review environment could not run Podman (`/run/user/1000/libpod` was
read-only). Its host OpenCode was `1.1.53`, not the pinned `1.18.34`, so it was not
used to claim runtime compatibility. Mermaid tests check fences and known
semicolon syntax issues; no Mermaid renderer was available to prove rendering.
