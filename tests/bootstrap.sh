#!/bin/sh
set -eu

for file in scripts/run-analysis scripts/container-entrypoint; do
  sh -n "$file"
done
python3 -m json.tool config/opencode/opencode.json >/dev/null
python3 -m json.tool schemas/finding.schema.json >/dev/null
python3 -m json.tool schemas/run.schema.json >/dev/null

sh -n scripts/network-guard scripts/start-burp
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
mkdir -p "$tmpdir/output"
cat > "$tmpdir/output/findings.jsonl" <<'JSON'
{"id":"F-EXAMPLE-1","title":"Example","asset":"source/app.py","evidence":["E-EXAMPLE-1"],"confidence":"low","severity":"informational","verification_status":"unverified","discovered_by":"fixture","recommendation":"Review manually."}
JSON
./scripts/validate-output "$tmpdir/output" >/dev/null
