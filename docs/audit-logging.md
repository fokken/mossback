# Audit logging

Each launch receives a unique `mossback-…` run ID. Logs are metadata-first; prompt/response body capture is not enabled. No debug logging, header dumps or authorization values are added by the proxy.

## Operator-owned logs

`AUDIT_LOG_DIR` defaults to a sibling of output, e.g. `output-audit/`. It must be separate from input/output and is never mounted into the analyzer. Each run contains:

```text
<run-id>/
  run.json             # Endpoint, model, scope paths, start/end/status
  execution.jsonl      # Network/guard/proxy/analysis/cleanup lifecycle
  proxy/access.jsonl   # Nginx request metadata
```

Endpoint metadata includes the pinned IPv4 address, original TLS server name,
API style and `public_llm_opt_in`. Local-only is the default; public opt-in is
recorded explicitly without recording the provider credential.

This operator `run.json` is a lifecycle record, **not** an instance of
`schemas/run.schema.json`: it lacks assessment fields such as `timestamp` and
`analysis_modules`, and contains endpoint/lifecycle fields instead. The
entrypoint separately writes `output/run-context.json` with run ID and model.
Schema-compatible `output/run.json`, tool-version inventories and input hashes
are not currently generated automatically. Do not copy the operator record
into output and assume it satisfies the assessment schema.

Nginx records run ID, request ID, UTC-offset timestamp, method, allowed route,
status, byte counts and request/upstream timings. Unknown routes are logged as
`denied`, not the raw attacker-controlled URI/query. Authorization and request
bodies are not logged. SSE requests are logged when they finish, not once per
token. Failed or disconnected requests still produce access-log status records.

Nginx can write only its proxy log subdirectory. Launcher events and metadata
remain host-owned. Log directories are created with restrictive permissions.
This is separation from the analyzer, not protection from the host operator.
Retain/rotate host log directories according to the assessment's retention policy.

## Analyzer logs

`output/logs/<run-id>/runtime.jsonl` records entrypoint stages and optional Burp
readiness. OpenCode's log directory points to `output/logs/<run-id>/opencode/`,
so application logs persist during the run. INFO is selected by default. The
application's own `role=server` records can describe session, tool, provider and
permission activity depending on the pinned version. Its process IDs are
separate from our run ID; the containing directory associates them.

Burp output, when enabled, is `output/logs/<run-id>/burp.log`. Agents are instructed
to keep a compact task journal with checks, outcomes and evidence IDs in
`output/logs/analysis-actions.jsonl`. This journal is best-effort agent output.

Only application logs are persisted, not OpenCode auth/session databases.
Runtime/tool logs may contain artifact excerpts or sensitive error details;
treat them as assessment data. Analyzer logs are writable by the analyzer and
are not tamper-proof. Native logs and timestamps provide useful flow visibility,
but do not guarantee an exhaustive, request-by-request tool transcript.

`completed` in operator metadata means the foreground process exited with code
zero, not that findings or the report are complete. Cleanup commands are
best-effort; `cleanup_completed` means they were attempted, not that all Podman
removals succeeded. Check for leftover resources after an interrupted/failed run.
