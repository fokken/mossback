"""Static integration checks; live MCP/OpenCode enforcement needs deployment tests."""
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WireMcpTests(unittest.TestCase):
    def test_stdio_server_has_no_runtime_installation(self):
        config = json.loads((ROOT / "config/opencode/opencode.json").read_text())
        server = config["mcp"]["servers"]["wiremcp"]
        self.assertEqual(server["type"], "local")
        self.assertEqual(server["command"], ["node", "/opt/wiremcp/index.js"])
        self.assertEqual(server["cwd"], "/audit/work")
        self.assertFalse(server["codemode"])
        self.assertEqual(server["timeout"]["execution"], 120000)

    def test_global_policy_allows_only_saved_capture_analysis(self):
        rules = json.loads((ROOT / "config/opencode/opencode.json").read_text())["permissions"]
        for tool in ("analyze_pcap", "capture_packets", "get_summary_stats", "get_conversations",
                     "check_threats", "check_ip_threats", "extract_credentials", "future_tool"):
            effect = None
            for rule in rules:
                if fnmatch.fnmatchcase("wiremcp_" + tool, rule["action"]):
                    effect = rule["effect"]
            self.assertEqual(effect, "allow" if tool == "analyze_pcap" else "deny", tool)

    def test_only_pcap_agent_is_allowed_access(self):
        for agent in (ROOT / "config/agents").glob("*.md"):
            frontmatter = agent.read_text().split("---", 2)[1]
            self.assertIn('action: wiremcp_*, resource: "*", effect: deny', frontmatter)
            self.assertEqual('action: wiremcp_analyze_pcap, resource: "*", effect: allow' in frontmatter,
                             agent.stem == "pcap-analyst")

    def test_installer_rejects_unpinned_refs_before_downloading(self):
        for commit in ("", "main", "abcd", "0" * 39 + ";"):
            with self.subTest(commit=commit):
                result = subprocess.run(["sh", str(ROOT / "scripts/install-wiremcp")],
                                        env={**os.environ, "WIREMCP_COMMIT": commit},
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
        installer = (ROOT / "scripts/install-wiremcp").read_text()
        self.assertIn("--ignore-scripts", installer)
        self.assertIn('rev-parse HEAD)" = "$WIREMCP_COMMIT"', installer)


if __name__ == "__main__":
    unittest.main()
