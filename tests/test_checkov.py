"""Validate Checkov offline command construction without requiring Checkov."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("checkov_offline", str(ROOT / "tools/source/checkov-offline"))
spec = importlib.util.spec_from_loader(loader.name, loader)
checkov = importlib.util.module_from_spec(spec)
loader.exec_module(checkov)


class CheckovTests(unittest.TestCase):
    def test_scan_uses_trusted_offline_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input", Path(directory) / "output"
            (source / "infra").mkdir(parents=True)
            output.mkdir()
            environment = {"BC_API_KEY": "secret", "CKV_EXTERNAL_CHECKS_DIR": "/untrusted",
                           "DOWNLOAD_EXTERNAL_MODULES": "true", "PYTHONPATH": "/untrusted"}
            with patch.object(checkov, "INPUT", source), patch.object(checkov, "OUTPUT", output), \
                    patch.dict(os.environ, environment), \
                    patch.object(checkov.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as run:
                destination = output / "checkov.json"
                self.assertEqual(checkov.scan(source / "infra", destination), 1)
                command = run.call_args.args[0]
                for flag in ("--skip-download", "--skip-results-upload", "--config-file"):
                    self.assertIn(flag, command)
                self.assertEqual(command[command.index("--download-external-modules") + 1], "false")
                self.assertNotIn("--external-checks-dir", command)
                for key in environment:
                    self.assertNotIn(key, run.call_args.kwargs["env"])
                self.assertEqual(run.call_args.kwargs["timeout"], 300)
                self.assertNotIn("shell", run.call_args.kwargs)
                with self.assertRaises(FileExistsError):
                    checkov.scan(source / "infra", destination)

    def test_outside_paths_are_rejected_before_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input", Path(directory) / "output"
            source.mkdir()
            output.mkdir()
            outside = Path(directory) / "outside"
            outside.mkdir()
            (source / "link").symlink_to(outside)
            with patch.object(checkov, "INPUT", source), patch.object(checkov, "OUTPUT", output), \
                    patch.object(checkov.subprocess, "run") as run:
                for artifact, destination in ((outside, output / "one.json"),
                                               (source / "link", output / "two.json"),
                                               (source, outside / "three.json")):
                    with self.assertRaises(ValueError):
                        checkov.scan(artifact, destination)
                run.assert_not_called()
