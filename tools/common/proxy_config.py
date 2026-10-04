"""Validate operator configuration and render immutable network policies."""
import ipaddress
import re


def endpoint(host, port):
    address = ipaddress.ip_address(host)
    if address.version != 4:
        raise ValueError("V1 supports IPv4 LLM endpoints")
    private = any(address in ipaddress.ip_network(net) for net in
                  ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    if not private:
        raise ValueError("LLM_HOST must be a routable private IPv4 address; loopback is inside the container")
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError("LLM_PORT must be between 1 and 65535")
    return str(address), port


def addresses(subnet, host):
    network = ipaddress.ip_network(subnet, strict=True)
    private = network.version == 4 and any(network.subnet_of(ipaddress.ip_network(net))
                 for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    if network.version != 4 or network.prefixlen != 29 or not private:
        raise ValueError("ANALYSIS_SUBNET must be a private IPv4 /29 network")
    if ipaddress.ip_address(host) in network:
        raise ValueError("ANALYSIS_SUBNET overlaps the LLM endpoint")
    return str(network.network_address + 2), str(network.network_address + 3)


def nginx_config(template, host, port, run_id, key="", tls=False):
    host, port = endpoint(host, port)
    if not re.fullmatch(r"[a-z0-9-]+", run_id):
        raise ValueError("invalid run ID")
    # No Nginx variable expansion, escapes, or config injection in credentials.
    if key and not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", key):
        raise ValueError("LLM_API_KEY contains unsupported characters")
    values = {
        "RUN_ID": run_id,
        "UPSTREAM": f"{'https' if tls else 'http'}://{host}:{port}",
        "UPSTREAM_HOST": f"{host}:{port}",
        "AUTHORIZATION": f"Bearer {key}" if key else "",
        "TLS_SETTINGS": ("proxy_ssl_verify on; proxy_ssl_trusted_certificate "
                         "/etc/ssl/certs/ca-certificates.crt;" if tls else ""),
    }
    for name, value in values.items():
        template = template.replace(f"@@{name}@@", value)
    if "@@" in template:
        raise ValueError("unresolved Nginx configuration placeholder")
    return template


def firewall(role, analyzer, proxy, host, port):
    host, port = endpoint(host, port)
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
