"""Upstream pin selection tests use fixtures, never network requests."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("resolve_build", ROOT / "scripts/resolve_build.py")
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ResolverTests(unittest.TestCase):
    def response(self, url):
        if "hub.docker.com" in url:
            return {"digest": "sha256:" + "a" * 64}
        if "registry.npmjs.org" in url:
            return {"version": "1.2.3"}
        if "pypi.org" in url:
            return {"info": {"version": "3.3.20"}}
        if "/commits/" in url:
            return {"sha": "b" * 40}
        return {"tag_name": "codeql-bundle-v2.27.1", "assets": [
            {"name": "codeql-bundle-linux64.tar.zst", "digest": "sha256:" + "c" * 64},
            {"name": "codeql-bundle-linux-arm64.tar.zst", "digest": "sha256:" + "d" * 64}]}

    def test_architecture_specific_pins(self):
        for architecture, checksum in (("x86_64", "c" * 64), ("aarch64", "d" * 64)):
            with patch.object(resolver.platform, "machine", return_value=architecture), \
                    patch.object(resolver, "metadata", side_effect=self.response):
                config = resolver.resolve_latest()
                self.assertEqual(config["CODEQL_BUNDLE_SHA256"], checksum)
                self.assertEqual(config["CHECKOV_VERSION"], "3.3.20")
                self.assertEqual(config["WIREMCP_COMMIT"], "b" * 40)

    def test_missing_digest_fails_closed(self):
        with patch.object(resolver.platform, "machine", return_value="x86_64"), \
                patch.object(resolver, "metadata", return_value={}):
            with self.assertRaises(ValueError):
                resolver.resolve_latest()
