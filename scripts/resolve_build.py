"""Host-only upstream pin resolution; no builds or analyzer network changes."""
import json
import platform
from urllib.request import Request, urlopen


def metadata(url):
    request = Request(url, headers={"User-Agent": "mossback-build-resolver", "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        if not response.url.startswith("https://"):
            raise ValueError("upstream redirected outside HTTPS")
        data = response.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024:
        raise ValueError("upstream metadata exceeds size limit")
    return json.loads(data)


def resolve_latest():
    arch = {"x86_64": "linux64", "amd64": "linux64", "aarch64": "linux-arm64", "arm64": "linux-arm64"}.get(platform.machine().lower())
    if not arch:
        raise ValueError("CodeQL requires an amd64 or arm64 build host")
    result = {}
    for key, repository, tag in (("BASE_IMAGE", "kalilinux/kali-rolling", "latest"),
                                 ("PROXY_BASE_IMAGE", "library/debian", "trixie-slim")):
        info = metadata(f"https://hub.docker.com/v2/repositories/{repository}/tags/{tag}")
        digest = info.get("digest")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ValueError(f"registry did not provide an index digest for {repository}:{tag}")
        result[key] = f"docker.io/{repository}:{tag}@{digest}"
    result["OPENCODE_VERSION"] = metadata("https://registry.npmjs.org/opencode-ai/latest")["version"]
    for key, package in (("SEMGREP_VERSION", "semgrep"), ("PYGHIDRA_MCP_VERSION", "pyghidra-mcp"),
                         ("CHECKOV_VERSION", "checkov")):
        result[key] = metadata(f"https://pypi.org/pypi/{package}/json")["info"]["version"]
    for key, repository, branch in (("SEMGREP_RULES_COMMIT", "semgrep/semgrep-rules", "develop"),
                                    ("WIREMCP_COMMIT", "0xKoda/WireMCP", "main")):
        result[key] = metadata(f"https://api.github.com/repos/{repository}/commits/{branch}")["sha"]
    release = metadata("https://api.github.com/repos/github/codeql-action/releases/latest")
    if not release["tag_name"].startswith("codeql-bundle-v"):
        raise ValueError("latest CodeQL Action release is not a bundle; select the bundle manually")
    result["CODEQL_BUNDLE_TAG"] = release["tag_name"]
    asset = next((item for item in release["assets"] if item["name"] == f"codeql-bundle-{arch}.tar.zst"), None)
    if not asset or not str(asset.get("digest", "")).startswith("sha256:"):
        raise ValueError("CodeQL release lacks the architecture-specific archive SHA256; verify manually")
    result["CODEQL_BUNDLE_SHA256"] = asset["digest"].removeprefix("sha256:")
    return result
