# Offline source analysis tools

Downloads happen only during image construction. Semgrep is installed in its own virtual environment and exposed on PATH. The image clones [semgrep/semgrep-rules](https://github.com/semgrep/semgrep-rules) at a full commit ID into `/opt/semgrep-rules`, retaining Git metadata and license files. The read-only root filesystem protects this checkout during analysis.

## Build inputs

Supply these environment variables before running the README build command:

- `SEMGREP_VERSION`: exact Semgrep release from [PyPI](https://pypi.org/project/semgrep/).
- `SEMGREP_RULES_COMMIT`: reviewed 40-character commit from the community rules repository.
- `CODEQL_BUNDLE_TAG`: release tag such as `codeql-bundle-v2.23.0`, from [github/codeql-action releases](https://github.com/github/codeql-action/releases).
- `CODEQL_BUNDLE_SHA256`: trusted SHA256 for that release's `codeql-bundle-linux64.tar.zst` (amd64) or `codeql-bundle-linux-arm64.tar.zst` (arm64). Obtain it from the release metadata through a trusted channel.

The build fails on missing pins or a mismatched checksum. CodeQL includes compatible, precompiled query packs so no runtime pack download is required. Selected rules and bundle identifiers are recorded in `/opt/mossback/source-tools.lock`. Apt and Python transitive dependencies are still resolved during the build; these pins alone do not guarantee byte-for-byte reproducibility.

## Interactive usage

Inside the running container:

```sh
semgrep --version
semgrep-offline --json --output /audit/output/evidence/semgrep.json /audit/input/source
codeql version
codeql resolve packs
codeql database analyze /audit/work/codeql-db \
  codeql/python-queries:codeql-suites/python-security-and-quality.qls \
  --format=sarif-latest --output=/audit/output/evidence/codeql.sarif
```

`semgrep-offline` selects the bundled Community Edition language directories and disables metrics and update checks. The full clone remains available, including Pro-only rules; the wrapper excludes those and non-rule YAML in repository metadata. Use local configurations rather than registry names or `--config auto`. Rule findings are evidence for investigation, not automatically confirmed vulnerabilities.

Use prebuilt CodeQL databases or extraction modes that do not execute the project's build scripts. Do not use automatic builds or artifact-supplied build commands on hostile source. Keep writable databases and caches in `/audit/work`. Semgrep caches, CodeQL configuration, and OpenCode state use the ephemeral home/cache directories configured by the entrypoint.

CodeQL use is subject to the [GitHub CodeQL terms](https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md); installation does not grant unrestricted use on private/commercial projects. Rule licenses are preserved with the checkout.

Run `sh /opt/mossback/tests/source-tools-smoke.sh` inside the container to verify Semgrep execution and CodeQL pack discovery.
