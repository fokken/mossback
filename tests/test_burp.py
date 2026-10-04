"""Checks for the optional Burp capability's filesystem and tool boundaries."""
import json
import fnmatch
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BurpBoundaryTests(unittest.TestCase):
    def test_external_project_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project.burp"
            project.write_bytes(b"original project")
            link = Path(directory) / "linked.burp"
            link.symlink_to(project)
            for path in (project, link):
                result = subprocess.run(
                    ["sh", str(ROOT / "scripts/start-burp")],
                    env={**os.environ, "BURP_PROJECT": str(path)},
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 64)
                self.assertIn("must resolve below /audit/input", result.stderr)
            self.assertEqual(project.read_bytes(), b"original project")

    def test_burp_only_exposes_read_tools_by_default(self):
        config = json.loads((ROOT / "config/opencode/opencode.json").read_text())
        self.assertFalse(config["mcp"]["burp"]["enabled"])
        permissions = config["permission"]
        for action in ("burp_send_http1_request", "burp_send_http2_request",
                       "burp_set_user_options", "burp_set_project_options",
                       "burp_generate_collaborator_payload", "burp_unknown_future_tool"):
            effect = None
            for pattern, decision in permissions.items():
                if fnmatch.fnmatchcase(action, pattern):
                    effect = decision
            self.assertEqual(effect, "deny", action)
        allowed = [action for action, effect in permissions.items() if effect == "allow" and action.startswith("burp_")]
        self.assertTrue(allowed)
        self.assertTrue(all(action.startswith("burp_get_") for action in allowed))

    def test_only_mcp_extension_loaded(self):
        config = json.loads((ROOT / "config/burp/user-options.json").read_text())
        extensions = config["user_options"]["extender"]["extensions"]
        self.assertEqual(len(extensions), 1)
        self.assertEqual(extensions[0]["extension_file"], "/opt/burp/burp-mcp-all.jar")
        project = json.loads((ROOT / "config/burp/project-options.json").read_text())
        self.assertEqual(project["proxy"]["request_listeners"], [])


if __name__ == "__main__":
    unittest.main()
