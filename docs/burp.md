# Burp project analysis

Burp is optional in the universal image. Supply trusted software separately from assessment artifacts. The launcher mounts the software read-only at `/opt/burp`; Burp runs inside the same network-restricted container as OpenCode, with loopback and the LLM proxy reachable. No ports are published, display sockets mounted, or target access granted.

## Supply the runtime

Prepare a dedicated host directory containing:

```text
burp-runtime/
  burp-suite.jar       # Licensed Burp distribution supplied by you
  burp-mcp-all.jar     # PortSwigger MCP Server extension
  mcp-proxy-all.jar    # Matching SSE-to-stdio proxy
```

Keep this directory disjoint from input, output, custom rules and operator logs.
The launcher currently rejects overlaps with input, rules and operator logs,
but **does not reject output overlap**. Check this yourself before running;
a read-only runtime mount is not protected if the same host files are also
reachable through writable output. See [verification gaps](verification.md).

Use matching reviewed builds of [PortSwigger/mcp-server](https://github.com/PortSwigger/mcp-server). The Burp application JAR alone does not provide MCP. The extension exposes a local SSE server; its proxy provides OpenCode's stdio connection. Ghidra's installed JDK supplies Java; verify compatibility with your Burp release.

```sh
BURP_RUNTIME_DIR=/absolute/path/burp-runtime \
BURP_PROJECT=/audit/input/burp/assessment.burp \
LLM_HOST=192.168.1.50 LLM_PORT=8080 LLM_MODEL=your-model \
  ./scripts/run-analysis ./artifacts ./analysis-output
```

`BURP_PROJECT` is a container path under `/audit/input`. Symlinks resolving outside that area are rejected. The container's `start-burp` script copies the project to `/audit/work/burp/project.burp` and loads that copy, leaving the original read-only. The copy and temporary state disappear when the container exits; Burp diagnostics persist in `/audit/output/logs/<run-id>/burp.log`.

## Configuration

- `config/burp/launch.json`: Java heap, fixed loopback MCP URL and startup timeout.
- `config/burp/project-options.json`: removes ordinary proxy listeners.
- `config/burp/user-options.json`: loads only the supplied MCP extension, disables BApp auto-updates, and requests paused tasks at startup.
- `config/opencode/opencode.json`: optional stdio proxy plus a deny-by-default Burp tool policy allowing history, Organizer, and scanner-issue reads.

The entrypoint enables the OpenCode connection only after Burp responds with SSE headers. Saved scans are not explicitly resumed. The extension's settings are persisted through Burp's extension storage, not through this JSON template: verify loopback binding, disabled configuration editing, and data-access approvals with your chosen extension version. Do not confuse application configuration with extension configuration.

## Verification still required

The configuration templates and launch flags require testing with your supplied Burp version. Project-file support requires an appropriate edition/license. Headless startup can stop for first-run license, project-password, or extension approval dialogs. A fresh headless session may also require preparation of the extension's history-access permissions. We do not automate license acceptance or mount your host Burp profile; if startup times out, inspect `burp.log` and prepare the chosen distribution for offline use.

The official extension includes active tools. OpenCode's permissions limit usage while the namespace firewall prevents external target access. Loopback remains reachable inside the analyzer; its processes share one OS boundary. No active testing is authorized by this integration.

Reference: [Burp command-line options](https://portswigger.net/burp/documentation/desktop/troubleshooting/launch-from-command-line).
