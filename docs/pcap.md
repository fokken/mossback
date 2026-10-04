# Offline PCAP analysis

The universal image includes TShark and capinfos for saved PCAP/PCAPNG analysis.
No MCP server is needed. Put captures in `artifacts/pcap/` and launch normally;
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

## WireMCP integration assessment

[WireMCP](https://github.com/0xKoda/WireMCP) is not enabled in this bootstrap.
Its current upstream server mixes saved-capture analysis with live capture,
external threat-feed requests and raw credential extraction. Its PCAP handler
interpolates an unrestricted file path into a shell command. An integration
must first remove incompatible tools server-side, replace shell interpolation
with argument-array subprocesses, confine files to assessment paths, disable
name resolution, bound processing and persist evidence. OpenCode tool denials
alone are not sufficient hardening. A reviewed offline-only adaptation can
reuse the deterministic tools installed here without granting network access.
