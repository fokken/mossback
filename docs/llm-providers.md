# LLM providers

Local LLMs remain the default. Public providers are an explicit exception to
local-only handling: assessment content included in model requests leaves your
environment. Obtain authorization for the data and review provider retention,
privacy and billing before opting in. Never send secrets or restricted evidence.

## Local OpenAI-compatible server

```sh
export LLM_HOST=192.168.1.50 LLM_PORT=8080 LLM_MODEL=your-model
export LLM_ALLOW_PUBLIC=0 LLM_TLS=0 LLM_API_STYLE=openai-compatible
./scripts/run-analysis ./artifacts ./analysis-output
```

Use a reachable private IPv4 address, not localhost. Set `LLM_TLS=1` when your
local server supports a certificate verifiable by the proxy's CA trust store.

## Public HTTPS endpoint

For an OpenAI-compatible service exposing `/v1/chat/completions`:

```sh
export LLM_ALLOW_PUBLIC=1 LLM_TLS=1
export LLM_HOST=api.provider.example LLM_PORT=443
export LLM_API_STYLE=openai-compatible LLM_MODEL=approved-model-id
# Supply LLM_API_KEY privately via your secret manager or shell environment.
./scripts/run-analysis ./artifacts ./analysis-output
```

For OpenAI, use `LLM_HOST=api.openai.com`, `LLM_PORT=443` and
`LLM_API_STYLE=openai`, selecting an approved model ID. This chooses OpenCode's
native `@ai-sdk/openai` provider, which uses `/v1/responses`. The compatible style
uses `@ai-sdk/openai-compatible` and `/v1/chat/completions`.
See [OpenCode provider configuration](https://opencode.ai/docs/providers/) and
[OpenAI API authentication](https://developers.openai.com/api/reference/overview).
Claude requires an OpenAI-compatible gateway; native Anthropic endpoints are
not supported by this proxy. Models must support the tool calls needed by agents.

`LLM_HOST` is a hostname or IPv4 address, **not** a URL. Arbitrary base paths,
query parameters and non-Bearer authentication are not supported. The runtime
always receives the internal proxy `/v1` URL, not the public endpoint or real key.
The current model configuration reserves 32,768 context tokens and 4,096 output
tokens; review these limits for your selected model before rebuilding.

## Boundary and audit behavior

Public mode requires verified HTTPS. The host resolves a DNS name once, rejects
non-global IPv4 answers and pins one address for the run. The original name is
used for TLS certificate verification, SNI and HTTP Host. Restart if the provider
rotates addresses; there is no runtime DNS, redirect following or broad egress.
Only the proxy can reach that exact IP/port. Analyzer egress remains restricted
to the proxy; all other destinations remain denied.

The real API key lives only in the temporary proxy configuration. Operator audit
metadata records public opt-in, server identity and pinned IP, while request logs
record timing, routes and statuses without bodies or credentials. These controls
restrict destinations, **not content**: the configured provider receives model
requests and can return untrusted content. This is not a data-loss-prevention
filter or proof of provider-side privacy.
