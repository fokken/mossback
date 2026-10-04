# OpenCode configuration

The entrypoint copies native OpenCode configuration and Markdown agents into the ephemeral workspace, then substitutes `LLM_MODEL`. The launcher sets `LLM_BASE_URL` to the restricted Nginx TCP proxy. Configure the endpoint outside the analyzer with `LLM_HOST`, `LLM_PORT` and optional `LLM_API_KEY`. Local endpoints are the default; see [public provider configuration](../../docs/llm-providers.md) for explicit opt-in.

Pin `OPENCODE_VERSION` during the image build and verify the configuration against that release. The provider uses OpenAI-compatible `/v1` semantics; the API credential is injected by Nginx, not passed to OpenCode or MCP servers.

The bundled `pyghidra` MCP server runs locally over stdio. Its configured project directory is `/audit/work/ghidra-projects`; agents must select binary inputs from `/audit/input`. This is configuration and agent policy, not server-enforced filesystem confinement.

The default static-analyst coordinates source-analyst, binary-analyst, burp-analyst, pcap-analyst and reporter. Source and PCAP shell commands require operator approval. WireMCP is denied globally; only pcap-analyst permits its saved-capture analysis tool. These runtime permissions do not create separate OS sandboxes within the universal image. See `config/agents-policy.md` for evidence and audit expectations and [verification gaps](../../docs/verification.md) before deployment.
