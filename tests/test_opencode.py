"""Native configuration shape and selected role boundaries; not a runtime test."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OpenCodeTests(unittest.TestCase):
    def test_native_provider_and_disabled_builtin_agents(self):
        config = json.loads((ROOT / "config/opencode/opencode.json").read_text())
        self.assertNotIn("providers", config)
        self.assertNotIn("permissions", config)
        self.assertNotIn("servers", config["mcp"])
        self.assertFalse(config["autoupdate"])
        self.assertEqual(config["share"], "disabled")
        self.assertEqual(config["enabled_providers"], ["mossback"])
        for agent in ("build", "plan", "general", "explore"):
            self.assertTrue(config["agent"][agent]["disable"])
        provider = config["provider"]["mossback"]
        self.assertEqual(provider["npm"], "@ai-sdk/openai-compatible")
        self.assertEqual(provider["options"]["apiKey"], "proxy-managed")
        self.assertEqual(config["permission"]["edit"]["/audit/work/.config/**"], "deny")

    def test_role_permissions_are_native_and_explicit(self):
        agents = {}
        for path in (ROOT / "config/agents").glob("*.md"):
            frontmatter = path.read_text().split("---", 2)[1]
            agents[path.stem] = json.loads(frontmatter.split("permission: ", 1)[1].strip())
        self.assertEqual(agents["source-analyst"]["bash"], "ask")
        self.assertEqual(agents["binary-analyst"]["pyghidra_*"], "allow")
        self.assertEqual(agents["reporter"]["read"]["*"], "deny")
        for role, rules in agents.items():
            if role != "binary-analyst":
                self.assertEqual(rules["pyghidra_*"], "deny")
            if role != "static-analyst":
                self.assertEqual(rules["task"], "deny")
        self.assertEqual(agents["static-analyst"]["task"]["*"], "deny")


if __name__ == "__main__":
    unittest.main()
