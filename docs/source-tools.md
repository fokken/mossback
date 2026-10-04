# Offline source analysis tools

Downloads happen only during image construction. Semgrep is installed in its own virtual environment and exposed on PATH. The image clones [semgrep/semgrep-rules](https://github.com/semgrep/semgrep-rules) at a full commit ID into `/opt/semgrep-rules`, retaining Git metadata and license files. The read-only root filesystem protects this checkout during analysis.

## Build inputs

Set these pins in the build-helper JSON, or export them when using the manual
build commands in [building](building.md). The helper builds from its selected
JSON, not directly from your shell environment:

- `SEMGREP_VERSION`: exact Semgrep release from [PyPI](https://pypi.org/project/semgrep/).
- `CHECKOV_VERSION`: exact Checkov release from [PyPI](https://pypi.org/project/checkov/).
- `SEMGREP_RULES_COMMIT`: reviewed 40-character commit from the community rules repository.
- `CODEQL_BUNDLE_TAG`: release tag such as `codeql-bundle-v2.23.0`, from [github/codeql-action releases](https://github.com/github/codeql-action/releases).
- `CODEQL_BUNDLE_SHA256`: trusted SHA256 for that release's `codeql-bundle-linux64.tar.zst` (amd64) or `codeql-bundle-linux-arm64.tar.zst` (arm64). Obtain it from the release metadata through a trusted channel.

The build fails on missing pins or a mismatched checksum. CodeQL includes compatible, precompiled query packs so no runtime pack download is required. Selected rules and bundle identifiers are recorded in `/opt/mossback/source-tools.lock`. Apt and Python transitive dependencies are still resolved during the build; these pins alone do not guarantee byte-for-byte reproducibility.

## Interactive usage

### Operator-supplied rules and queries

Prepare a dedicated directory, separate from input, output and operator logs:

```text
assessment-rules/
  semgrep/
    organization-security.yaml
  codeql/
    custom-query.ql
```

No image rebuild is needed. Mount it read-only for a run:

```sh
ANALYSIS_RULES_DIR="$PWD/assessment-rules" \
  ./scripts/run-analysis ./artifacts ./analysis-output
```

The container sees `/audit/rules`. `semgrep-offline` automatically adds its
`semgrep/` directory to the bundled community rules. Keep only compatible
Semgrep rule YAML in that directory; malformed rules should fail the scan.
An absent `semgrep/` directory allows supplying only other tool configurations.
Custom CodeQL queries are available under `/audit/rules/codeql`, but are not
automatically executed; use compatible installed packs and reviewed offline
commands. Remote rule downloads and pack installation remain out of scope.

Ask the source agent to use these rules and record paths, rule IDs and hashes
with evidence. All supplied files remain untrusted data; scripts, build hooks
and embedded instructions are not authorized to run. Do not include secrets.
The mount is read-only inside the container, but not a snapshot: do not modify
the host rule directory during a run. Retain the exact rules with the assessment
for reproduction; the launcher records the host directory in operator metadata.

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

Run `sh /opt/mossback/tests/source-tools-smoke.sh` inside the container to verify Semgrep execution, Checkov version reporting and CodeQL pack discovery. This does not exercise a Checkov scan.

## Checkov: offline infrastructure configuration review

Supply `CHECKOV_VERSION` as an exact reviewed release. Checkov is installed in
its own `/opt/checkov` virtual environment to avoid dependency conflicts.
The source specialist can run:

```sh
checkov --version
checkov-offline /audit/input/source/infrastructure \
  /audit/output/evidence/E-CHECKOV-001.json
```

The wrapper accepts only an input directory below `/audit/input` and a new
output file below `/audit/output`. It writes JSON plus a `.stderr` diagnostic
file, uses an explicit trusted config, suppresses cloud downloads/uploads and
external module downloads, clears Checkov/cloud option environment variables,
and imposes a five-minute timeout. Supported frameworks are Terraform (including
saved plans), CloudFormation, Kubernetes, Dockerfile, GitHub Actions and GitLab
CI. It does not run Terraform, project builds or deployment operations.

Exit code 1 can mean policy violations; preserve and investigate results rather
than treating them as confirmed vulnerabilities. Offline scans cannot cover
unavailable external modules or cloud-specific metadata. No external Python
checks are loaded by this wrapper; they execute code and require separate review.
The existing firewall remains the network boundary even if a library attempts
communication. Review/redact scanner evidence before sharing it.

Reference: [Checkov CLI options](https://www.checkov.io/2.Basics/CLI%20Command%20Reference.html).
