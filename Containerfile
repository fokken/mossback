# Supply a reviewed, immutable digest at build time; do not use a floating base tag.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG OPENCODE_VERSION
ARG PYGHIDRA_MCP_VERSION=0.2.7
ARG SEMGREP_VERSION
ARG CHECKOV_VERSION
ARG SEMGREP_RULES_COMMIT
ARG CODEQL_BUNDLE_TAG
ARG CODEQL_BUNDLE_SHA256
ARG WIREMCP_COMMIT
COPY scripts/install-wiremcp /opt/mossback/install-wiremcp
RUN test -n "$OPENCODE_VERSION" && test -n "$PYGHIDRA_MCP_VERSION" \
 && test -n "$SEMGREP_VERSION" && test -n "$SEMGREP_RULES_COMMIT" \
 && test -n "$CHECKOV_VERSION" \
 && test -n "$CODEQL_BUNDLE_TAG" && test -n "$CODEQL_BUNDLE_SHA256" \
 && test -n "$WIREMCP_COMMIT" \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      binutils binwalk ca-certificates curl file ghidra git jq libimage-exiftool-perl nodejs npm \
      python3 python3-venv radare2 rizin ripgrep socat tshark wireshark-common yara zstd \
 && npm install --global --ignore-scripts "opencode-ai@${OPENCODE_VERSION}" \
 && sh /opt/mossback/install-wiremcp \
 && python3 -m venv /opt/pyghidra-mcp \
 && /opt/pyghidra-mcp/bin/pip install --no-cache-dir "pyghidra-mcp==${PYGHIDRA_MCP_VERSION}" \
 && python3 -m venv /opt/semgrep \
 && /opt/semgrep/bin/pip install --no-cache-dir "semgrep==${SEMGREP_VERSION}" \
 && python3 -m venv /opt/checkov \
 && /opt/checkov/bin/pip install --no-cache-dir "checkov==${CHECKOV_VERSION}" \
 && apt-get purge -y --auto-remove npm \
 && rm -rf /var/lib/apt/lists/* /root/.npm /root/.cache

COPY scripts/install-source-tools /opt/mossback/install-source-tools
RUN sh /opt/mossback/install-source-tools
ENV PATH="/opt/checkov/bin:/opt/semgrep/bin:/opt/codeql:${PATH}" \
    SEMGREP_RULES_DIR=/opt/semgrep-rules \
    SEMGREP_SEND_METRICS=off \
    SEMGREP_ENABLE_VERSION_CHECK=0

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin analyst \
 && mkdir -p /audit/input /audit/work /audit/output /run/llm \
 && chown -R analyst:analyst /audit /run/llm

COPY --chown=analyst:analyst config /opt/mossback/config
COPY schemas /opt/mossback/schemas
COPY --chown=analyst:analyst scripts/container-entrypoint /usr/local/bin/container-entrypoint
COPY tools/source/semgrep-offline /usr/local/bin/semgrep-offline
COPY tools/source/checkov-offline /usr/local/bin/checkov-offline
COPY tools/pcap/pcap-offline /usr/local/bin/pcap-offline
COPY scripts/start-burp /usr/local/bin/start-burp
COPY tests/source-tools-smoke.sh /opt/mossback/tests/source-tools-smoke.sh
COPY tests/fixtures /opt/mossback/tests/fixtures
COPY tests/network-probe.py /opt/mossback/tests/network-probe.py
RUN chmod 0555 /usr/local/bin/container-entrypoint
RUN chmod 0555 /usr/local/bin/semgrep-offline
RUN chmod 0555 /usr/local/bin/checkov-offline
RUN chmod 0555 /usr/local/bin/start-burp
RUN chmod 0555 /usr/local/bin/pcap-offline \
 && if [ -f /usr/bin/dumpcap ]; then chmod 000 /usr/bin/dumpcap; fi

USER analyst:analyst
ENV GHIDRA_INSTALL_DIR=/usr/share/ghidra
WORKDIR /audit/work
ENTRYPOINT ["/usr/local/bin/container-entrypoint"]
