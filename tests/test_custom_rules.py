"""Check local config argument construction without requiring installed Semgrep."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CustomRulesTests(unittest.TestCase):
    def test_wrapper_combines_custom_and_bundled_local_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bundled = base / "bundled"
            (bundled / "python").mkdir(parents=True)
            custom = base / "custom rules"
            custom.mkdir()
            executable = base / "semgrep"
            executable.write_text("#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
            executable.chmod(0o700)
            environment = {**os.environ, "PATH": str(base) + os.pathsep + os.environ["PATH"],
                           "SEMGREP_RULES_DIR": str(bundled), "SEMGREP_CUSTOM_RULES_DIR": str(custom)}
            command = ["sh", str(ROOT / "tools/source/semgrep-offline"), "--json", "/audit/input/source"]
            result = subprocess.run(command, env=environment, capture_output=True, text=True, check=True)
            args = json.loads(result.stdout)
            self.assertEqual(args[args.index(str(custom)) - 1], "--config")
            self.assertIn(str(bundled / "python"), args)
            self.assertIn("--metrics=off", args)
            self.assertIn("--disable-version-check", args)
            custom.rmdir()
            custom.write_text("not a directory")
            result = subprocess.run(command, env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 64)


if __name__ == "__main__":
    unittest.main()
