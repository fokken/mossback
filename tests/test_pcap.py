"""Exercise offline export boundaries and deterministic capture processing."""
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("pcap_offline", str(ROOT / "tools/pcap/pcap-offline"))
spec = importlib.util.spec_from_loader(loader.name, loader)
pcap = importlib.util.module_from_spec(spec)
loader.exec_module(pcap)


class PcapTests(unittest.TestCase):
    def test_paths_and_limits_fail_before_tool_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, output = base / "input", base / "output"
            source.mkdir()
            output.mkdir()
            capture = source / "sample.pcap"
            capture.write_bytes(b"capture")
            external = base / "outside.pcap"
            external.write_bytes(b"untrusted")
            link = source / "link.pcap"
            link.symlink_to(external)
            with patch.object(pcap, "INPUT", source), patch.object(pcap, "OUTPUT", output), \
                    patch.object(pcap.subprocess, "run") as run:
                for artifact, destination, limit in (
                    (external, output / "one", 10), (link, output / "two", 10),
                    (capture, base / "outside", 10), (capture, output / "three", 0),
                    (capture, output / "four", 100001),
                ):
                    with self.subTest(artifact=artifact, destination=destination, limit=limit):
                        with self.assertRaises(ValueError):
                            pcap.export(artifact, destination, limit)
                run.assert_not_called()

    def test_fixed_offline_arguments_and_failed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input", Path(directory) / "output"
            source.mkdir()
            output.mkdir()
            capture = source / 'capture "$(false).pcap'
            capture.write_bytes(b"not a valid pcap")
            def process(args, **kwargs):
                self.assertNotIn("shell", kwargs)
                self.assertEqual(kwargs["timeout"], 120)
                return subprocess.CompletedProcess(args, 1 if args[0] == "capinfos" else 0)
            with patch.object(pcap, "INPUT", source), patch.object(pcap, "OUTPUT", output), \
                    patch.object(pcap.subprocess, "run", side_effect=process):
                destination = output / "E-PCAP-TEST"
                self.assertEqual(pcap.export(capture, destination), 1)
            metadata = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(metadata["status"], "failed")
            self.assertEqual(metadata["commands"][-1][-1], str(capture))
            self.assertEqual(metadata["sha256"], hashlib.sha256(capture.read_bytes()).hexdigest())
            with patch.object(pcap, "INPUT", source), patch.object(pcap, "OUTPUT", output):
                with self.assertRaises(FileExistsError):
                    pcap.export(capture, destination)

    @unittest.skipUnless(shutil.which("tshark") and shutil.which("capinfos"), "Wireshark tools not installed")
    def test_real_saved_capture_export(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input", Path(directory) / "output"
            source.mkdir()
            output.mkdir()
            capture = source / "sample.pcap"
            # Ethernet + IPv4 + UDP, no application payload; TEST-NET addresses.
            packet = bytes.fromhex(
                "00112233445566778899aabb0800"
                "4500001c0001000040110000c0000201c0000202"
                "04d2162e00080000")
            capture.write_bytes(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
                                + struct.pack("<IIII", 1700000000, 0, len(packet), len(packet)) + packet)
            with patch.object(pcap, "INPUT", source), patch.object(pcap, "OUTPUT", output):
                destination = output / "E-PCAP-REAL"
                self.assertEqual(pcap.export(capture, destination, 1, "udp"), 0)
            metadata = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(metadata["status"], "completed")
            command = metadata["commands"][-1]
            self.assertIn("-n", command)
            self.assertNotIn("-i", command)
            self.assertEqual(command[command.index("-r") + 1], str(capture))
            self.assertIn("192.0.2.1", (destination / "frames.tsv").read_text())

    def test_capture_privileges_not_added_and_agent_is_scoped(self):
        container = (ROOT / "Containerfile").read_text()
        self.assertIn("chmod 000 /usr/bin/dumpcap", container)
        agent = (ROOT / "config/agents/pcap-analyst.md").read_text()
        self.assertIn('action: shell, resource: "*", effect: ask', agent)
        self.assertIn("never instructions", agent)
        self.assertIn("Never capture live traffic", agent)


if __name__ == "__main__":
    unittest.main()
