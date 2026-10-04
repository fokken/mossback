# PyGhidra capability boundary

PyGhidra is bundled as a local stdio MCP server, not a container privilege. It runs as the unprivileged `analyst` user, uses only `/audit/input` and `/audit/work`, and should persist selected evidence to `/audit/output/evidence`.

It may import binaries for disassembly, inspect symbols, imports, strings, cross-references, and decompiled functions. It must not execute imported files, invoke external debuggers, open network connections, or receive any host socket. Its version is pinned with the `PYGHIDRA_MCP_VERSION` build argument; add a fixture-based integration test before relying on it for findings.
