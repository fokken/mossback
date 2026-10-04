"""Run explicitly in the analyzer namespace on the deployment host."""
import http.client
import socket
import sys

proxy, upstream, port, gateway = sys.argv[1:]
with socket.create_connection((proxy, 8080), timeout=3):
    print("allowed: proxy TCP port 8080")
for host, target_port in ((upstream, int(port)), (proxy, 8081), (gateway, 80),
                          ("169.254.169.254", 80), ("1.1.1.1", 443)):
    try:
        with socket.create_connection((host, target_port), timeout=2):
            raise SystemExit(f"ISOLATION FAILED: unexpected connection to {host}:{target_port}")
    except OSError:
        print(f"blocked: {host}:{target_port}")
for method, path in (("GET", "/admin"), ("GET", "/v1/models?destination=elsewhere"),
                     ("CONNECT", "example.com:443")):
    connection = http.client.HTTPConnection(proxy, 8080, timeout=3)
    connection.request(method, path)
    response = connection.getresponse()
    if response.status not in (400, 403, 405):
        raise SystemExit(f"API POLICY FAILED: {method} {path}: {response.status}")
    response.read()
    connection.close()
print("Analyzer isolation and proxy route probes passed")
