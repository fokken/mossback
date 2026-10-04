"""Host orchestration for the restricted TCP proxy and interactive analyzer."""
import argparse
from datetime import datetime, timezone
import json
import ipaddress
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/common"))
from proxy_config import addresses, upstream_endpoint, firewall, nginx_config


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def mount(source, target, readonly=False):
    if any(c in str(source) for c in (",", "\n", "\r")):
        raise ValueError("mount paths cannot contain commas or newlines")
    return ["--mount", f"type=bind,src={source},dst={target},relabel=private" + (",ro" if readonly else "")]


class Run:
    def __init__(self, audit, run_id):
        self.audit, self.run_id = audit, run_id
        self.containers, self.networks = [], []
        self.environment = dict(os.environ)
        self.environment.pop("LLM_API_KEY", None)

    def event(self, action, **fields):
        with (self.audit / "execution.jsonl").open("a") as stream:
            stream.write(json.dumps(dict(timestamp=timestamp(), run_id=self.run_id,
                                         action=action, **fields)) + "\n")

    def command(self, *args, check=True):
        result = subprocess.run(["podman", *map(str, args)], env=self.environment,
                                capture_output=True, text=True)
        if check and result.returncode:
            raise RuntimeError(f"Podman {args[0]} failed: {result.stderr.strip()}")
        return result

    def network(self, name, *options):
        self.command("network", "create", "--disable-dns", *options, name)
        self.networks.append(name)
        self.event("network_created", name=name)

    def detached(self, name, *args):
        self.containers.append(name)
        self.command("run", "--detach", "--pull=never", "--name", name, *args)
        self.event("container_started", name=name)

    def guard(self, name, policy, networks, image):
        self.detached(name, *networks, "--userns=keep-id:uid=10001,gid=10001", "--user=0:0",
                      "--cap-drop=ALL", "--cap-add=NET_ADMIN", "--cap-add=SETPCAP",
                      "--security-opt=no-new-privileges", "--read-only", "--pids-limit=16",
                      "--memory=64m", "--cpus=0.25", *mount(policy, "/run/firewall.nft", True),
                      image, "/usr/local/bin/network-guard")
        for _ in range(50):
            if "NETWORK_POLICY_READY" in self.command("logs", name).stdout:
                status = self.command("exec", name, "cat", "/proc/1/status").stdout
                values = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
                if any(int(values[field].strip(), 16) for field in
                       ("CapEff", "CapPrm", "CapBnd", "CapAmb", "CapInh")):
                    raise RuntimeError("network guard retained capabilities")
                self.event("network_policy_ready", name=name, capabilities="none")
                return
            if self.command("inspect", "--format={{.State.Running}}", name).stdout.strip() != "true":
                raise RuntimeError(f"network guard {name} failed to apply firewall")
            time.sleep(0.1)
        raise RuntimeError("network guard startup timed out")

    def cleanup(self):
        for name in reversed(self.containers):
            self.command("rm", "--force", name, check=False)
        for name in reversed(self.networks):
            self.command("network", "rm", name, check=False)
        self.event("cleanup_completed")


def main():
    parser = argparse.ArgumentParser(description="LLM_HOST=IP LLM_PORT=PORT LLM_MODEL=model run-analysis INPUT OUTPUT")
    parser.add_argument("--check-isolation", action="store_true", help="run TCP/API boundary probes instead of OpenCode")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("opencode_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        public_setting = os.environ.get("LLM_ALLOW_PUBLIC", "0")
        if public_setting not in ("0", "1"):
            raise ValueError("LLM_ALLOW_PUBLIC must be 0 or 1")
        allow_public = public_setting == "1"
        api_style = os.environ.get("LLM_API_STYLE", "openai-compatible")
        if api_style not in ("openai-compatible", "openai"):
            raise ValueError("LLM_API_STYLE must be openai-compatible or openai")
        model = os.environ.get("LLM_MODEL", "")
        if not model:
            raise ValueError("LLM_MODEL is required")
        tls = os.environ.get("LLM_TLS", "1" if allow_public else "0")
        if tls not in ("0", "1"):
            raise ValueError("LLM_TLS must be 0 or 1")
        host, port, server_name = upstream_endpoint(os.environ.get("LLM_HOST", ""),
                                                   os.environ.get("LLM_PORT", ""), allow_public, tls == "1")
        subnet = os.environ.get("ANALYSIS_SUBNET", "10.203.0.0/29")
        analyzer_ip, proxy_ip = addresses(subnet, host)
        source, output = args.input.resolve(strict=True), args.output.resolve()
        audit_parent = Path(os.environ.get("AUDIT_LOG_DIR", str(output) + "-audit")).resolve()
        if not source.is_dir() or not disjoint(source, output):
            raise ValueError("INPUT_DIR and OUTPUT_DIR must be disjoint directories")
        if not disjoint(audit_parent, source) or not disjoint(audit_parent, output):
            raise ValueError("AUDIT_LOG_DIR must be separate from input and output")
        runtime_value, project = os.environ.get("BURP_RUNTIME_DIR", ""), os.environ.get("BURP_PROJECT", "")
        if bool(runtime_value) != bool(project):
            raise ValueError("BURP_RUNTIME_DIR and BURP_PROJECT must be supplied together")
        runtime = Path(runtime_value).resolve(strict=True) if runtime_value else None
        if runtime and (not runtime.is_dir() or not disjoint(runtime, source) or not disjoint(runtime, audit_parent)):
            raise ValueError("Burp runtime must be separate from artifacts and audit logs")
        rules_value = os.environ.get("ANALYSIS_RULES_DIR", "")
        rules = Path(rules_value).resolve(strict=True) if rules_value else None
        if rules and (not rules.is_dir() or any(not disjoint(rules, path)
                                              for path in (source, output, audit_parent, runtime) if path)):
            raise ValueError("ANALYSIS_RULES_DIR must be a directory separate from input, output, audit logs and Burp runtime")
        for path in (source, output, audit_parent, runtime, rules):
            if path:
                mount(path, "/check")
        run_id = "mossback-" + uuid.uuid4().hex[:16]
        config = nginx_config((ROOT / "config/proxy/nginx.conf.template").read_text(),
                              host, port, run_id, os.environ.get("LLM_API_KEY", ""), tls == "1",
                              allow_public, server_name, api_style)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    os.umask(0o077)
    audit = audit_parent / run_id
    audit.mkdir(parents=True)
    (audit / "proxy").mkdir()
    for name in ("findings", "evidence", "reports", "logs"):
        (output / name).mkdir(parents=True, exist_ok=True)
    run = Run(audit, run_id)
    started = timestamp()
    metadata = dict(run_id=run_id, start_time=started, model=model, status="running",
                    llm_host=host, llm_port=port, tls=tls == "1", input=str(source), output=str(output))
    metadata.update(llm_server_name=server_name, public_llm_opt_in=allow_public, api_style=api_style)
    if rules:
        metadata["analysis_rules_dir"] = str(rules)
    proxy_image = os.environ.get("PROXY_IMAGE", "mossback-proxy:local")
    analyzer_image = os.environ.get("ANALYZER_IMAGE", "mossback:local")
    exit_code = 1
    print(f"Run: {run_id}\nOperator audit logs: {audit}", flush=True)
    if allow_public:
        print("WARNING: public LLM opt-in permits sending assessment content to the configured provider.",
              file=sys.stderr, flush=True)
    run.event("run_started", llm_host=host, llm_port=port, model=model,
              public_llm_opt_in=allow_public, llm_server_name=server_name, api_style=api_style)
    (audit / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    try:
        if run.command("info", "--format={{.Host.Security.Rootless}}").stdout.strip() != "true":
            raise RuntimeError("rootless Podman is required")
        for image in (proxy_image, analyzer_image):
            run.command("image", "exists", image)
        with tempfile.TemporaryDirectory(prefix="mossback-proxy-") as directory:
            temporary = Path(directory)
            for role in ("analyzer", "proxy"):
                policy = temporary / f"{role}.nft"
                policy.write_text(firewall(role, analyzer_ip, proxy_ip, host, port, allow_public))
                policy.chmod(0o644)
            nginx = temporary / "nginx.conf"
            nginx.write_text(config)
            internal, egress = run_id + "-internal", run_id + "-egress"
            run.network(internal, "--internal", f"--subnet={subnet}")
            run.network(egress)
            analyzer_guard, proxy_guard = run_id + "-analyzer-net", run_id + "-proxy-net"
            run.guard(analyzer_guard, temporary / "analyzer.nft", [f"--network={internal}:ip={analyzer_ip}"], proxy_image)
            run.guard(proxy_guard, temporary / "proxy.nft", [f"--network={internal}:ip={proxy_ip}", f"--network={egress}"], proxy_image)
            common = ["--userns=keep-id:uid=10001,gid=10001", "--user=10001:10001",
                      "--cap-drop=ALL", "--security-opt=no-new-privileges", "--read-only"]
            proxy = run_id + "-proxy"
            run.detached(proxy, *common, f"--network=container:{proxy_guard}", "--pids-limit=64",
                         "--memory=256m", "--cpus=0.5",
                         "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001",
                         *mount(nginx, "/run/proxy/nginx.conf", True),
                         *mount(audit / "proxy", "/var/log/llm-proxy"), proxy_image)
            for _ in range(50):
                if run.command("exec", proxy, "curl", "--noproxy", "*", "--fail", "--silent", "--max-time", "1",
                               "http://127.0.0.1:8080/healthz", check=False).returncode == 0:
                    break
                if run.command("inspect", "--format={{.State.Running}}", proxy).stdout.strip() != "true":
                    raise RuntimeError("Nginx exited during startup")
                time.sleep(0.1)
            else:
                raise RuntimeError("Nginx startup timed out")
            run.event("proxy_ready", proxy_ip=proxy_ip)
            container = run_id + "-analyzer"
            run.containers.append(container)
            command = ["podman", "run", "--rm", "--pull=never", "--interactive", "--tty", "--name", container,
                       *common, f"--network=container:{analyzer_guard}", "--pids-limit=256", "--memory=4g", "--cpus=2",
                       "--ulimit=nofile=1024:1024", "--ulimit=fsize=1073741824:1073741824",
                       "--tmpfs=/audit/work:rw,nosuid,nodev,noexec,size=4g,uid=10001,gid=10001",
                       "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=256m,uid=10001,gid=10001",
                       *mount(source, "/audit/input", True), *mount(output, "/audit/output"),
                       "--env", f"LLM_BASE_URL=http://{proxy_ip}:8080/v1", "--env", f"LLM_MODEL={model}",
                       "--env", f"ANALYSIS_RUN_ID={run_id}"]
            command.extend(["--env", f"LLM_API_STYLE={api_style}"])
            if runtime:
                command.extend([*mount(runtime, "/opt/burp", True), "--env", f"BURP_PROJECT={project}"])
            if rules:
                command.extend([*mount(rules, "/audit/rules", True),
                                "--env", "SEMGREP_CUSTOM_RULES_DIR=/audit/rules/semgrep"])
            if args.check_isolation:
                command.extend(["--entrypoint=python3", analyzer_image, "/opt/mossback/tests/network-probe.py",
                                proxy_ip, host, str(port), str(ipaddress.ip_network(subnet).network_address + 1)])
            else:
                command.extend([analyzer_image, *args.opencode_args])
            run.event("analysis_started", container=container)
            exit_code = subprocess.run(command, env=run.environment).returncode
            run.event("analysis_exited", exit_code=exit_code)
    except KeyboardInterrupt:
        exit_code = 130
        run.event("run_interrupted")
    except (RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        run.event("run_failed", error_type=type(error).__name__)
    finally:
        run.cleanup()
        metadata.update(end_time=timestamp(), status="completed" if exit_code == 0 else "failed", exit_code=exit_code)
        (audit / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    def terminate(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    raise SystemExit(main())
