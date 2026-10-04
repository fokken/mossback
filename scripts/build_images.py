"""Configure and build mossback images with explicit, reviewed build inputs."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?"
DIGEST = r"[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}"
SPECS = {
    "BASE_IMAGE": (DIGEST, "Kali image reference with reviewed SHA256 digest"),
    "PROXY_BASE_IMAGE": (DIGEST, "Debian proxy image reference with reviewed SHA256 digest"),
    "OPENCODE_VERSION": (VERSION, "Exact OpenCode version supporting the native config schema"),
    "PYGHIDRA_MCP_VERSION": (VERSION, "Exact PyGhidra MCP version"),
    "SEMGREP_VERSION": (VERSION, "Exact Semgrep version"),
    "CHECKOV_VERSION": (VERSION, "Exact Checkov version"),
    "SEMGREP_RULES_COMMIT": (r"[0-9a-f]{40}", "Reviewed community rules Git commit"),
    "WIREMCP_COMMIT": (r"[0-9a-f]{40}", "Reviewed upstream WireMCP Git commit"),
    "CODEQL_BUNDLE_TAG": (r"codeql-bundle-v[0-9]+\.[0-9]+\.[0-9]+", "CodeQL bundle release tag"),
    "CODEQL_BUNDLE_SHA256": (r"[0-9a-f]{64}", "CodeQL archive SHA256 for this build architecture"),
}
IMAGE_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._:/-]*"
DEFAULTS = {"PYGHIDRA_MCP_VERSION": "0.2.7", "ANALYZER_IMAGE": "mossback:local",
            "PROXY_IMAGE": "mossback-proxy:local"}


def validate(config):
    allowed = set(SPECS) | {"ANALYZER_IMAGE", "PROXY_IMAGE"}
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValueError("build configuration must contain only documented build settings, never credentials")
    result = {**DEFAULTS, **config}
    for key, (pattern, _) in SPECS.items():
        value = result.get(key)
        if not isinstance(value, str) or not re.fullmatch(pattern, value):
            raise ValueError(f"{key} is missing or invalid; supply an exact reviewed value")
    for key in ("ANALYZER_IMAGE", "PROXY_IMAGE"):
        if not isinstance(result[key], str) or not re.fullmatch(IMAGE_PATTERN, result[key]):
            raise ValueError(f"invalid {key}")
    if result["ANALYZER_IMAGE"] == result["PROXY_IMAGE"]:
        raise ValueError("analyzer and proxy image tags must differ")
    return result


def configure(path, existing):
    values = {}
    for key, (_, description) in SPECS.items():
        default = existing.get(key, os.environ.get(key, DEFAULTS.get(key, "")))
        value = input(f"{key}: {description}" + (f" [{default}]" if default else "") + ": ").strip()
        values[key] = value or default
    for key in ("ANALYZER_IMAGE", "PROXY_IMAGE"):
        default = existing.get(key, DEFAULTS[key])
        values[key] = input(f"{key} [{default}]: ").strip() or default
    configure_values(path, validate(values))
    print(f"Saved build settings to {path}. No images built yet.")


def configure_values(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".mossback-build-",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(values, stream, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def commands(config):
    proxy = ["podman", "build", "--file", str(ROOT / "Containerfile.proxy"),
             "--build-arg", "PROXY_BASE_IMAGE=" + config["PROXY_BASE_IMAGE"],
             "--tag", config["PROXY_IMAGE"], str(ROOT)]
    analyzer = ["podman", "build", "--file", str(ROOT / "Containerfile")]
    for key in SPECS:
        if key != "PROXY_BASE_IMAGE":
            analyzer.extend(["--build-arg", key + "=" + config[key]])
    analyzer.extend(["--tag", config["ANALYZER_IMAGE"], str(ROOT)])
    return proxy, analyzer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / ".mossback-build.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--configure", action="store_true", help="prompt for pins and save local JSON; do not build")
    mode.add_argument("--check", action="store_true", help="validate local settings without Podman or network access")
    mode.add_argument("--resolve-latest", action="store_true", help="resolve upstream pins over HTTPS and save JSON; do not build")
    args = parser.parse_args()
    try:
        if args.resolve_latest:
            from resolve_build import resolve_latest
            values = validate(resolve_latest())
            configure_values(args.config, values)
            print(f"Resolved current upstream build pins to {args.config}; review before building.")
            return 0
        if args.config.exists():
            existing = json.loads(args.config.read_text())
            if not isinstance(existing, dict):
                raise ValueError("build configuration must be a JSON object")
        elif args.configure:
            seed = ROOT / "mossback-build.json"
            existing = json.loads(seed.read_text()) if seed.exists() else {}
        else:
            raise ValueError("no build configuration; run scripts/build-images --configure first")
        if args.configure:
            configure(args.config, existing)
            return 0
        config = validate(existing)
        if args.check:
            print("Build settings valid. Versions, upstream checksums and compatibility still require operator review.")
            return 0
        rootless = subprocess.run(["podman", "info", "--format={{.Host.Security.Rootless}}"],
                                  check=True, capture_output=True, text=True)
        if rootless.stdout.strip() != "true":
            raise ValueError("rootless Podman is required; do not use sudo")
        for command in commands(config):
            print(f"Building {command[command.index('--tag') + 1]}", flush=True)
            subprocess.run(command, check=True)
        print("Images built. Next: configure the local LLM and run the isolation smoke test.")
        return 0
    except (ValueError, OSError, EOFError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Build failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
