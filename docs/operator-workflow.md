# Operator workflow

1. Build `mossback:local` with the pinned tool inputs documented in README
   and `docs/source-tools.md`. Build `mossback-proxy:local` from
   `Containerfile.proxy` with a reviewed `PROXY_BASE_IMAGE` digest.
2. Start the local OpenAI-compatible LLM on a private IPv4 address reachable
   from rootless Podman. Use its exact model ID and a tool-capable model.
3. Prepare separate input/output directories and, optionally, a trusted Burp
   runtime directory. Select a disjoint operator audit directory.
   To supply custom Semgrep rules or CodeQL queries, set `ANALYSIS_RULES_DIR`
   to a dedicated directory as described in [source tools](source-tools.md).
4. Configure the endpoint and launch:

```sh
export LLM_HOST=192.168.1.50
export LLM_PORT=8080
export LLM_MODEL=your-model
export AUDIT_LOG_DIR=/absolute/path/operator-audit
# Optional: LLM_API_KEY; LLM_TLS=1 for verified upstream HTTPS.
./scripts/run-analysis ./artifacts ./analysis-output
```

No Unix socket needs to be configured. `127.0.0.1` is container loopback, so use
a reachable private host/LAN address. The launcher prints the run ID and audit
path. It starts network guards, verifies their privileges were dropped, starts
Nginx and opens the OpenCode TUI. All resources created for this run are removed
on exit. Upstream connectivity is exercised when the first API request occurs.

5. Ask static-analyst to analyze a bounded scope. It delegates to source-analyst,
   binary-analyst, pcap-analyst and optional burp-analyst, then asks reporter to consolidate
   findings. Approve reviewed source-tool commands when prompted. Example:

> Review `/audit/input/source` for authentication and authorization weaknesses.
> Use the offline Semgrep rules, investigate relevant alerts, preserve evidence,
> then generate structured findings and a Markdown report. Keep unsupported
> claims unverified and record coverage gaps.

6. Inspect operator lifecycle/proxy logs alongside OpenCode runtime logs.
   Ensure evidence, findings and the report are saved in output before exiting;
   work databases and application session state are ephemeral.
   Agents must incrementally save reusable scripts/queries under
   `output/scripts/<run-id>/<agent>/` and selected important intermediates under
   `output/artifacts/<run-id>/<agent>/`, with a provenance/reproduction manifest.
   Review these exports as untrusted assessment data; saving a script does not
   authorize running it. Bulk databases/caches remain ephemeral by default.
7. Run `./scripts/validate-output ./analysis-output` and review the conclusions.
   The current validator performs partial structural checks on existing files;
   it does not guarantee completeness or confirm vulnerabilities.

For Burp, additionally set `BURP_RUNTIME_DIR` and container-path `BURP_PROJECT`
as documented in `docs/burp.md`. The MCP extension and licensing preparation
still require verification with your supplied distribution.

The full image and rootless networking integration need validation on the
deployment host. Do not deploy a configuration that skips firewall startup.

After building, run an explicit boundary smoke test:

```sh
./scripts/run-analysis --check-isolation ./artifacts ./analysis-output
```

This checks proxy TCP reachability, blocked direct destinations and denied API
routes instead of starting OpenCode. It does not replace verification of the
proxy's own egress policy or prove the full LLM/MCP workflow.
