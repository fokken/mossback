import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/common"))
from proxy_config import addresses, endpoint, firewall, nginx_config
spec = importlib.util.spec_from_file_location("launcher", ROOT / "scripts/run_analysis.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class ProxyConfigurationTests(unittest.TestCase):
    def test_endpoint_rejects_metadata_public_dns_and_injection(self):
        for host in ("169.254.169.254", "8.8.8.8", "localhost", "127.0.0.1",
                     "0.0.0.0", "224.0.0.1", "10.0.0.1; deny all", "::1"):
            with self.assertRaises(ValueError, msg=host):
                endpoint(host, "8080")
        for port in ("0", "65536", "123;", ""):
            with self.assertRaises(ValueError):
                endpoint("192.168.1.50", port)
        self.assertEqual(endpoint("192.168.1.50", "8080"), ("192.168.1.50", 8080))

    def test_network_cannot_overlap_upstream(self):
        with self.assertRaises(ValueError):
            addresses("10.203.0.0/29", "10.203.0.4")
        for subnet in ("127.0.0.0/29", "169.254.169.248/29", "0.0.0.0/29"):
            with self.assertRaises(ValueError):
                addresses(subnet, "192.168.1.50")

    def test_proxy_has_fixed_upstream_no_variable_credentials(self):
        template = (ROOT / "config/proxy/nginx.conf.template").read_text()
        rendered = nginx_config(template, "192.168.1.50", 8080, "test-run", "secret-test")
        self.assertIn("proxy_pass http://192.168.1.50:8080;", rendered)
        self.assertNotIn("proxy_pass $", rendered)
        self.assertIn("proxy_buffering off;", rendered)
        log_format = rendered.split("log_format audit", 1)[1].split("access_log", 1)[0]
        for value in ("secret-test", "$request_body", "$http_authorization", "$args", "$request_uri"):
            self.assertNotIn(value, log_format)
        for key in ('bad"; return 200;', "$http_authorization", "bad\nkey"):
            with self.assertRaises(ValueError):
                nginx_config(template, "192.168.1.50", 8080, "test-run", key)

    def test_firewall_limits_new_connections_and_blocks_forwarding(self):
        analyzer = firewall("analyzer", "10.203.0.2", "10.203.0.3", "192.168.1.50", 8080)
        proxy = firewall("proxy", "10.203.0.2", "10.203.0.3", "192.168.1.50", 8080)
        self.assertNotIn("192.168.1.50", analyzer)
        self.assertIn("ip daddr 10.203.0.3 tcp dport 8080 accept", analyzer)
        self.assertIn("ip daddr 192.168.1.50 tcp dport 8080 accept", proxy)
        for policy in (analyzer, proxy):
            self.assertEqual(policy.count("policy drop"), 3)


class LauncherTests(unittest.TestCase):
    def simulate(self, directory, retained=False):
        source, output = Path(directory) / "input", Path(directory) / "output"
        source.mkdir()
        calls = []

        def podman(command, **kwargs):
            calls.append((command, kwargs))
            self.assertNotIn("LLM_API_KEY", kwargs["env"])
            result = ""
            if command[1] == "info":
                result = "true\n"
            elif command[1] == "logs":
                result = "NETWORK_POLICY_READY\n"
            elif command[1] == "exec" and command[-1] == "/proc/1/status":
                result = "\n".join(f"{field}:\t{1 if retained else 0:016x}" for field in
                                   ("CapEff", "CapPrm", "CapBnd", "CapAmb", "CapInh"))
            return subprocess.CompletedProcess(command, 0, result, "")

        environment = {"LLM_HOST": "192.168.1.50", "LLM_PORT": "8080", "LLM_MODEL": "test",
                       "LLM_API_KEY": "secret-test"}
        with patch.dict(os.environ, environment, clear=True), patch.object(sys, "argv", ["run-analysis", str(source), str(output)]), \
                patch.object(launcher.subprocess, "run", side_effect=podman):
            status = launcher.main()
        return status, calls, next((Path(str(output) + "-audit")).iterdir())

    def test_full_lifecycle_hides_credentials_and_audit_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            status, calls, audit = self.simulate(directory)
            self.assertEqual(status, 0)
            analyzer = next(cmd for cmd, _ in calls if "--interactive" in cmd)
            self.assertIn("--cap-drop=ALL", analyzer)
            self.assertIn("--read-only", analyzer)
            self.assertTrue(any(arg.startswith("--network=container:") for arg in analyzer))
            self.assertFalse(any("secret-test" in arg or str(audit) in arg for arg in analyzer))
            events = [json.loads(line)["action"] for line in (audit / "execution.jsonl").read_text().splitlines()]
            self.assertLess(events.index("network_policy_ready"), events.index("analysis_started"))
            self.assertIn("cleanup_completed", events)
            self.assertEqual(json.loads((audit / "run.json").read_text())["status"], "completed")

    def test_guard_retaining_capabilities_prevents_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            status, calls, audit = self.simulate(directory, retained=True)
            self.assertEqual(status, 1)
            self.assertFalse(any("--interactive" in cmd for cmd, _ in calls))
            self.assertTrue(any(cmd[1:3] == ["rm", "--force"] for cmd, _ in calls))
            self.assertEqual(json.loads((audit / "run.json").read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
