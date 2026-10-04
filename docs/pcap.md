# Offline PCAP analysis

The universal image includes TShark and capinfos for saved PCAP/PCAPNG analysis.
WireMCP supplies saved-capture context over stdio MCP. Put captures in
`artifacts/pcap/` and launch normally;
the coordinator can delegate to `pcap-analyst`.

Example operator request:

> Inspect `/audit/input/pcap/assessment.pcapng` for cleartext exposure and
> suspicious exchanges. Preserve evidence with frame references, distinguish
> observations from confirmed findings, and report coverage limitations.

The agent requests approval for deterministic shell commands. Start with:

```sh
pcap-offline /audit/input/pcap/assessment.pcapng \
  /audit/output/evidence/E-PCAP-001 --packet-limit 10000 --filter 'tcp || udp'
```

The destination must be new. The wrapper exports capture metadata, a bounded
frame table, parser diagnostics, tool version and a SHA256/provenance manifest.
It requires a regular input file under `/audit/input`, writes only under
`/audit/output`, uses fixed subprocess arguments without a shell and imposes
a 120-second timeout per parser command. Packet limits count input packets
before display filtering; capinfos inspects the full capture within its timeout.
Larger captures require reviewed follow-up queries and explicit coverage notes.

For focused follow-up, use `tshark -n -r` with display filters and minimal fields.
Do not resolve names, capture interfaces, replay traffic, load untrusted
dissectors, or run extracted content. The image disables the dumpcap executable;
no capture capabilities, host interfaces or new network permissions are granted.
This is not a separate parser sandbox: Wireshark still processes hostile bytes
inside the existing analyzer boundary. Keep the image's packages reviewed.

Default exports exclude application payloads, but endpoint metadata and parser
errors can still be sensitive. Review/redact persisted evidence before sharing.
Encrypted traffic, capture loss and unsupported protocols limit conclusions.
The specialist writes `output/findings/pcap.json`; reporter consolidates it with
other findings. Reusable scripts and selected exports follow the shared
preservation policy. Rebuild the analyzer image to install this capability.

References: [TShark manual](https://www.wireshark.org/docs/man-pages/tshark.html)
and [capinfos manual](https://www.wireshark.org/docs/man-pages/capinfos.html).

## Upstream WireMCP

Supply `WIREMCP_COMMIT` as a reviewed full 40-character Git commit and rebuild
with `--build-arg WIREMCP_COMMIT="$WIREMCP_COMMIT"`. The image installs unmodified
[WireMCP](https://github.com/0xKoda/WireMCP) at `/opt/wiremcp`; OpenCode starts it
locally with Node, without runtime downloads. Build-time npm lifecycle scripts
are disabled. The generated npm lockfile remains in the image; upstream uses
dependency ranges, so the source commit alone does not pin the complete build.

Only `wiremcp_analyze_pcap` is allowed, and other agents explicitly deny all
WireMCP tools. Live-capture, external threat-lookups and credential-extraction
tools remain registered upstream but are denied by OpenCode policy. Existing
namespace firewalls, disabled dumpcap, dropped capabilities and resource limits
are unchanged. Tool permissions must be verified with the pinned OpenCode
version; they are not separate OS isolation between agents.

Upstream interpolates capture paths into shell commands and does not enforce
assessment path confinement or use `-n`. Its response trimming happens after
parsing. These risks are not fixed by this integration. The agent must stage
captures using reviewed copy commands into simple agent-chosen work paths
before calling WireMCP, avoid attacker-controlled filenames, and preserve the
original capture hash. Failed name lookups cannot expand permitted egress.
The MCP timeout does not guarantee child-process termination; container exit
does. Prefer `pcap-offline` for bounded processing and persistent exports.

WireMCP may return sensitive HTTP host/URI metadata. Agents must redact and
save relevant evidence themselves; upstream does not provide durable exports.
Image build, stdio MCP startup and real OpenCode tool-policy enforcement still
require deployment verification with your selected versions.
