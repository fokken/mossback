"""Validate operator configuration and render immutable network policies."""
import ipaddress
import re
import socket


def endpoint(host, port, allow_public=False):
    address = ipaddress.ip_address(host)
    if address.version != 4:
        raise ValueError("V1 supports IPv4 LLM endpoints")
    private = any(address in ipaddress.ip_network(net) for net in
                  ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    public = address.is_global and not address.is_multicast and not address.is_reserved
    if not private and not (allow_public and public):
        raise ValueError("LLM_HOST must be a routable private IPv4 address; loopback is inside the container")
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("LLM_PORT must be between 1 and 65535")
    return str(address), port


def upstream_endpoint(host, port, allow_public=False, tls=False):
    """Resolve only on the host; pin one address and retain the TLS/Host identity."""
    if allow_public and not tls:
        raise ValueError("public LLM opt-in requires verified HTTPS (LLM_TLS=1)")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not allow_public:
            raise ValueError("local mode requires a private numeric IPv4 LLM_HOST")
        if not re.fullmatch(r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z][A-Za-z0-9-]{0,62}", host):
            raise ValueError("LLM_HOST must be a plain DNS hostname, not a URL")
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError("LLM_PORT must be between 1 and 65535")
        candidates = sorted({item[4][0] for item in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)})
        if not candidates or any(not ipaddress.IPv4Address(ip).is_global
                                 or ipaddress.IPv4Address(ip).is_multicast
                                 or ipaddress.IPv4Address(ip).is_reserved for ip in candidates):
            raise ValueError("public hostname must resolve exclusively to global IPv4 addresses")
        return endpoint(candidates[0], port, True)[0], port, host.lower()
    return (*endpoint(str(address), port, allow_public), str(address))


def addresses(subnet, host):
    network = ipaddress.ip_network(subnet, strict=True)
    private = network.version == 4 and any(network.subnet_of(ipaddress.ip_network(net))
                 for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    if network.version != 4 or network.prefixlen != 29 or not private:
        raise ValueError("ANALYSIS_SUBNET must be a private IPv4 /29 network")
    if ipaddress.ip_address(host) in network:
        raise ValueError("ANALYSIS_SUBNET overlaps the LLM endpoint")
    return str(network.network_address + 2), str(network.network_address + 3)


def nginx_config(template, host, port, run_id, key="", tls=False, allow_public=False,
                 server_name=None, api_style="openai-compatible"):
    host, port = endpoint(host, port, allow_public)
    if allow_public and not tls:
        raise ValueError("public LLM requires verified HTTPS")
    server_name = server_name or host
    if not re.fullmatch(r"[A-Za-z0-9.-]+", server_name):
        raise ValueError("invalid TLS server name")
    if api_style not in ("openai-compatible", "openai"):
        raise ValueError("unsupported LLM_API_STYLE")
    if not re.fullmatch(r"[a-z0-9-]+", run_id):
        raise ValueError("invalid run ID")
    # No Nginx variable expansion, escapes, or config injection in credentials.
    if key and not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", key):
        raise ValueError("LLM_API_KEY contains unsupported characters")
    values = {
        "RUN_ID": run_id,
        "UPSTREAM": f"{'https' if tls else 'http'}://{host}:{port}",
        "UPSTREAM_HOST": f"{server_name}:{port}",
        "AUTHORIZATION": f"Bearer {key}" if key else "",
        "TLS_SETTINGS": (f'proxy_ssl_server_name on; proxy_ssl_name "{server_name}"; '
                         "proxy_ssl_verify on; proxy_ssl_trusted_certificate "
                         "/etc/ssl/certs/ca-certificates.crt;" if tls else ""),
    }
    for name, value in values.items():
        template = template.replace(f"@@{name}@@", value)
    if "@@" in template:
        raise ValueError("unresolved Nginx configuration placeholder")
    return template


def firewall(role, analyzer, proxy, host, port, allow_public=False):
    host, port = endpoint(host, port, allow_public)
    analyzer = str(ipaddress.IPv4Address(analyzer))
    proxy = str(ipaddress.IPv4Address(proxy))
    if role == "analyzer":
        inbound = ""
        outbound = f"ip daddr {proxy} tcp dport 8080 accept"
    elif role == "proxy":
        inbound = f"ip saddr {analyzer} tcp dport 8080 accept"
        outbound = f"ip daddr {host} tcp dport {port} accept"
    else:
        raise ValueError("unknown firewall role")
    return f"""table inet mossback {{
  chain input {{
    type filter hook input priority 0; policy drop;
    iifname "lo" accept
    ct state established,related accept
    {inbound}
  }}
  chain output {{
    type filter hook output priority 0; policy drop;
    oifname "lo" accept
    ct state established,related accept
    {outbound}
  }}
  chain forward {{ type filter hook forward priority 0; policy drop; }}
}}
"""
