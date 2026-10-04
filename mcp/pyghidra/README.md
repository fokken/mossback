# PyGhidra capability boundary

PyGhidra is bundled as a local stdio MCP server, not a container privilege. It runs as the unprivileged `analyst` user. Agents must use `/audit/input` for binaries, `/audit/work/ghidra-projects` for projects and `/audit/output/evidence` for selected evidence. These paths are policy/configuration, not per-server OS confinement; MCP processes share the analyzer filesystem and namespace.

It may import binaries for disassembly, inspect symbols, imports, strings, cross-references, and decompiled functions. It must not execute imported files, invoke external debuggers, open network connections, or receive any host socket. Its version is pinned with the `PYGHIDRA_MCP_VERSION` build argument; add a fixture-based integration test before relying on it for findings.
