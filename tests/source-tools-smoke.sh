#!/bin/sh
set -eu
test -d /opt/semgrep-rules/.git
test -n "$(git -c safe.directory=/opt/semgrep-rules -C /opt/semgrep-rules rev-parse HEAD)"
test -f /opt/security-ai/source-tools.lock
semgrep --version
codeql version
codeql resolve packs --format=json > /audit/work/codeql-packs.json
jq -e 'type == "object" and length > 0' /audit/work/codeql-packs.json >/dev/null
semgrep scan --oss-only --metrics=off --disable-version-check --json \
  --config /opt/security-ai/tests/fixtures/semgrep-smoke.yaml \
  /opt/security-ai/tests/fixtures/semgrep-smoke.py > /audit/work/semgrep-smoke.json
jq -e '.errors | length == 0' /audit/work/semgrep-smoke.json >/dev/null
jq -e '.results | length == 1' /audit/work/semgrep-smoke.json >/dev/null
