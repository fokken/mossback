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
from proxy_config import addresses, endpoint, upstream_endpoint, firewall, nginx_config
spec = importlib.util.spec_from_file_location("launcher", ROOT / "scripts/run_analysis.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class ProxyConfigurationTests(unittest.TestCase):
    def test_public_requires_opt_in_tls_and_pinned_global_dns(self):
        for enabled, tls in ((False, True), (True, False)):
            with self.assertRaises(ValueError):
                upstream_endpoint("api.example.com", 443, enabled, tls)
        answers = [(2, 1, 6, "", ("8.8.8.8", 443))]
        with patch("proxy_config.socket.getaddrinfo", return_value=answers):
            self.assertEqual(upstream_endpoint("api.example.com", 443, True, True),
                             ("8.8.8.8", 443, "api.example.com"))
        for address in ("127.0.0.1", "169.254.169.254", "192.168.1.50"):
            mixed = answers + [(2, 1, 6, "", (address, 443))]
            with patch("proxy_config.socket.getaddrinfo", return_value=mixed):
                with self.assertRaises(ValueError):
                    upstream_endpoint("api.example.com", 443, True, True)

    def test_public_proxy_checks_identity_and_exact_egress(self):
        template = (ROOT / "config/proxy/nginx.conf.template").read_text()
        rendered = nginx_config(template, "8.8.8.8", 443, "test-run", "secret-test",
                                True, True, "api.example.com", "openai")
        self.assertIn('proxy_ssl_name "api.example.com";', rendered)
        self.assertIn("proxy_ssl_verify on;", rendered)
        self.assertIn('Host "api.example.com:443"', rendered)
        self.assertIn("proxy_pass https://8.8.8.8:443;", rendered)
        proxy = firewall("proxy", "10.203.0.2", "10.203.0.3", "8.8.8.8", 443, True)
        self.assertIn("ip daddr 8.8.8.8 tcp dport 443 accept", proxy)
        analyzer = firewall("analyzer", "10.203.0.2", "10.203.0.3", "8.8.8.8", 443, True)
        self.assertNotIn("8.8.8.8", analyzer)

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
    def simulate(self, directory, retained=False, custom_rules=False, public=False):
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
        if public:
            environment.update(LLM_HOST="8.8.8.8", LLM_PORT="443", LLM_ALLOW_PUBLIC="1",
                               LLM_API_STYLE="openai")
        if custom_rules:
            rules = Path(directory) / "rules"
            rules.mkdir()
            environment["ANALYSIS_RULES_DIR"] = str(rules)
        with patch.dict(os.environ, environment, clear=True), patch.object(sys, "argv", ["run-analysis", str(source), str(output)]), \
                patch.object(launcher.subprocess, "run", side_effect=podman):
            status = launcher.main()
        return status, calls, next((Path(str(output) + "-audit")).iterdir())

    def test_public_launch_records_opt_in_and_keeps_credentials_private(self):
        with tempfile.TemporaryDirectory() as directory:
            status, calls, audit = self.simulate(directory, public=True)
            self.assertEqual(status, 0)
            metadata = json.loads((audit / "run.json").read_text())
            self.assertTrue(metadata["public_llm_opt_in"])
            self.assertTrue(metadata["tls"])
            self.assertEqual(metadata["api_style"], "openai")
            analyzer = next(cmd for cmd, _ in calls if "--interactive" in cmd)
            self.assertIn("LLM_API_STYLE=openai", analyzer)
            self.assertFalse(any("secret-test" in arg or "8.8.8.8" in arg for arg in analyzer))

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

    def test_custom_rules_are_readonly_and_only_mounted_in_analyzer(self):
        with tempfile.TemporaryDirectory() as directory:
            status, calls, audit = self.simulate(directory, custom_rules=True)
            self.assertEqual(status, 0)
            analyzer = next(cmd for cmd, _ in calls if "--interactive" in cmd)
            rules_mount = next(arg for arg in analyzer if "dst=/audit/rules," in arg)
            self.assertTrue(rules_mount.endswith(",ro"))
            self.assertIn("SEMGREP_CUSTOM_RULES_DIR=/audit/rules/semgrep", analyzer)
            self.assertFalse(any("dst=/audit/rules" in arg for cmd, _ in calls
                                 if "--interactive" not in cmd for arg in cmd))
            self.assertEqual(json.loads((audit / "run.json").read_text())["analysis_rules_dir"],
                             str(Path(directory) / "rules"))

    def test_custom_rules_cannot_overlap_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input"
            source.mkdir()
            rules = Path(directory) / "rules"
            rules.mkdir()
            environment = {"LLM_HOST": "192.168.1.50", "LLM_PORT": "8080", "LLM_MODEL": "test",
                           "ANALYSIS_RULES_DIR": str(rules)}
            with patch.dict(os.environ, environment, clear=True), \
                    patch.object(sys, "argv", ["run-analysis", str(source), str(rules / "output")]), \
                    patch.object(launcher.subprocess, "run") as podman:
                with self.assertRaises(SystemExit) as error:
                    launcher.main()
                self.assertEqual(error.exception.code, 2)
                podman.assert_not_called()


if __name__ == "__main__":
    unittest.main()
