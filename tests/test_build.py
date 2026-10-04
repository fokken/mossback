"""Build configuration and command tests without downloads or image mutations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_images", ROOT / "scripts/build_images.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def settings():
    return dict(BASE_IMAGE="docker.io/kalilinux/kali-rolling@sha256:" + "a" * 64,
                PROXY_BASE_IMAGE="docker.io/library/debian:bookworm-slim@sha256:" + "b" * 64,
                OPENCODE_VERSION="1.2.3", SEMGREP_VERSION="1.2.3", CHECKOV_VERSION="3.3.20",
                SEMGREP_RULES_COMMIT="a" * 40, WIREMCP_COMMIT="b" * 40,
                CODEQL_BUNDLE_TAG="codeql-bundle-v2.3.4", CODEQL_BUNDLE_SHA256="c" * 64)


class BuildTests(unittest.TestCase):
    def test_rejects_floating_pins_and_credentials(self):
        for key, value in (("BASE_IMAGE", "kali:latest"), ("WIREMCP_COMMIT", "main"),
                           ("OPENCODE_VERSION", "latest"), ("CODEQL_BUNDLE_SHA256", "REPLACE"),
                           ("LLM_API_KEY", "secret"), ("ANALYZER_IMAGE", "--privileged")):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    build.validate({**settings(), key: value})
        self.assertEqual(build.validate(settings())["PYGHIDRA_MCP_VERSION"], "0.2.7")

    def test_commands_use_repository_context_and_all_pins(self):
        config = build.validate(settings())
        proxy, analyzer = build.commands(config)
        self.assertEqual(proxy[-1], str(ROOT))
        self.assertEqual(analyzer[-1], str(ROOT))
        for key in build.SPECS:
            self.assertIn(key + "=" + config[key], proxy if key == "PROXY_BASE_IMAGE" else analyzer)
        self.assertNotIn("--privileged", analyzer)

    def test_configuration_is_private_json_without_tool_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "build.json"
            with patch("builtins.input", return_value=""), patch.object(build.subprocess, "run") as run:
                build.configure(destination, settings())
                run.assert_not_called()
            self.assertEqual(json.loads(destination.read_text()), build.validate(settings()))
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_check_uses_no_podman_and_nonrootless_build_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "build.json"
            destination.write_text(json.dumps(settings()))
            with patch.object(sys, "argv", ["build-images", "--config", str(destination), "--check"]), \
                    patch.object(build.subprocess, "run") as run:
                self.assertEqual(build.main(), 0)
                run.assert_not_called()
            with patch.object(sys, "argv", ["build-images", "--config", str(destination)]), \
                    patch.object(build.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "false\n")) as run:
                with self.assertRaises(SystemExit):
                    build.main()
                self.assertEqual(run.call_count, 1)

    def test_build_stops_at_first_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "build.json"
            destination.write_text(json.dumps(settings()))
            results = [subprocess.CompletedProcess([], 0, "true\n"),
                       subprocess.CalledProcessError(1, ["podman", "build"])]
            with patch.object(sys, "argv", ["build-images", "--config", str(destination)]), \
                    patch.object(build.subprocess, "run", side_effect=results) as run:
                with self.assertRaises(SystemExit):
                    build.main()
                self.assertEqual(run.call_count, 2)

    def test_resolution_failure_does_not_overwrite_configuration(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "build.json"
            original = json.dumps(settings())
            destination.write_text(original)
            resolver = SimpleNamespace(resolve_latest=lambda: {**settings(), "BASE_IMAGE": None})
            with patch.dict(sys.modules, {"resolve_build": resolver}), \
                    patch.object(sys, "argv", ["build-images", "--config", str(destination), "--resolve-latest"]), \
                    patch.object(build.subprocess, "run") as run:
                with self.assertRaises(SystemExit):
                    build.main()
                run.assert_not_called()
                self.assertEqual(destination.read_text(), original)


if __name__ == "__main__":
    unittest.main()
