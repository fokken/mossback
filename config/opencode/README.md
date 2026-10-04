# OpenCode configuration

The entrypoint copies the V2 configuration and Markdown agents into the ephemeral workspace, then substitutes `LLM_MODEL`. The launcher sets `LLM_BASE_URL` to the restricted Nginx TCP proxy. Configure the endpoint outside the analyzer with `LLM_HOST`, `LLM_PORT` and optional `LLM_API_KEY`.

Pin `OPENCODE_VERSION` during the image build and verify the configuration against that release. The provider uses OpenAI-compatible `/v1` semantics; the API credential is injected by Nginx, not passed to OpenCode or MCP servers.

The bundled `pyghidra` MCP server runs locally over stdio. It writes its Ghidra project data only below `/audit/work/ghidra-projects`; its binary inputs must be selected from `/audit/input`.

The default static-analyst coordinates source-analyst, binary-analyst, burp-analyst and reporter. These runtime permissions do not create separate OS sandboxes within the universal image. Source shell commands require operator approval. See `config/agents-policy.md` for evidence and audit expectations.
