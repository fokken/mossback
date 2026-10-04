# Network isolation

The analyzer connects by TCP only to Nginx; Nginx connects by TCP only to the configured private IPv4 `LLM_HOST:LLM_PORT`. Per-run rootless bridge networks provide internal analyzer/proxy transport and proxy-only egress. DNS is disabled and no ports are published. `ANALYSIS_SUBNET` defaults to `10.203.0.0/29`; change it if it conflicts with existing networks. IPv6 upstreams and hostnames are not supported in V1.

An internal network alone is not the security boundary. Each application joins a namespace held by a rootless guard. The guard installs nftables inet rules before application startup: analyzer output permits only proxy TCP port 8080; proxy output permits only the configured LLM IP/port. Proxy input permits only analyzer IP/port 8080. Established responses and local loopback are allowed. Forwarding and all unmatched input/output are denied, including IPv6.

Only guard setup receives NET_ADMIN (install namespace rules) and SETPCAP (remove capability bounding set). These are confined to rootless namespaces. Guards drop effective, permitted, inherited, ambient and bounding capabilities and become idle namespace holders. The launcher verifies all five sets are zero before applications start. Nginx and analyzer receive CAP_DROP=ALL. No host firewall is changed, no host network is used, and no privileged container is required. Firewall failure aborts startup.

Nginx allows exact GET `/v1/models` and POST `/v1/chat/completions` or `/v1/responses`. Unknown paths, queries, unsupported methods and upstream redirects are denied. A local health endpoint is available only on proxy loopback. The upstream is a validated numeric address. Response buffering is disabled for streaming. Optional `LLM_TLS=1` verifies the certificate against image CAs; it must match the configured IP.

Set `LLM_API_KEY` on the host only when needed. It is inserted into a temporary private Nginx config mounted only into the proxy and removed after the run. The upstream must be an operator-controlled local LLM, not another forwarding proxy. Public addresses and cloud metadata addresses are rejected. The credential does not enter analyzer or guard environments.

Deployment requires rootless Podman bridge networking, namespace sharing and working namespace nftables. Verify these on the deployment host; there is no permissive fallback. Loopback is shared by analyzer processes, so Burp and PyGhidra are not separate OS sandboxes. Operator audit logs are not mounted into the analyzer.
