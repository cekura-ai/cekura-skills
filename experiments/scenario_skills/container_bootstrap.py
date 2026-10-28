"""Container-only transport setup. The target runner and its model stay unchanged."""
import os
import json
import socket
import subprocess
import sys
from pathlib import Path


def restore_pi_settings(source, home):
    """Restore captured loader settings hidden by the disposable home mount."""
    data = Path(source).read_bytes()  # Missing capture must prevent runner startup.
    target = Path(home) / ".pi/agent/settings.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(0o644)
    return target


def main():
    fixture_port = str(int(os.environ["BENCHMARK_FIXTURE_PORT"]))
    proxy_port = str(int(os.environ["BENCHMARK_PROXY_PORT"]))
    proof_path = os.environ.get("BENCHMARK_NETWORK_GUARD_PROOF")
    if proof_path:
        from network_guard import validate_proof
        gateway = validate_proof(json.loads(Path(proof_path).read_text()), fixture_port, proxy_port)
    else:
        gateway = socket.gethostbyname("host.docker.internal")

    # Fail closed before the runner gets credentials. Only the host fixture/proxy
    # ports and in-container loopback are reachable.
    rules = [
        ["-F", "OUTPUT"], ["-P", "OUTPUT", "DROP"],
        ["-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"],
    ]
    for port in (fixture_port, proxy_port):
        rules.append(["-A", "OUTPUT", "-p", "tcp", "-d", gateway, "--dport", port, "-j", "ACCEPT"])
    # Legacy iptables needs a writable lock; the container root is read-only.
    firewall_env = dict(os.environ, XTABLES_LOCKFILE="/tmp/benchmark-xtables.lock")
    if not proof_path:
        subprocess.run(["ip6tables", "-P", "OUTPUT", "DROP"], check=True, env=firewall_env)
        # Policy must precede flush even in the native target path.
        rules[:2] = [["-P", "OUTPUT", "DROP"], ["-F", "OUTPUT"]]
        for rule in rules:
            subprocess.run(["iptables"] + rule, check=True, env=firewall_env)

    # Write as the home owner, avoiding DAC_OVERRIDE/CHOWN capabilities.
    os.setegid(1000)
    os.seteuid(1000)
    try:
        restore_pi_settings(os.environ["BENCHMARK_PI_SETTINGS_PATH"], "/home/agent")
    finally:
        os.seteuid(0)
        os.setegid(0)

    proxy_url = "http://%s:%s" % (gateway, proxy_port)
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,host.docker.internal," + gateway
    # Proxy support must be verified with the pinned Node, without upgrading it.
    os.environ["NODE_USE_ENV_PROXY"] = "1"
    if sys.argv[1:] == ["--probe-only"]:
        os.execvp("python3", ["python3", "/benchmark/image_probe.py", "--in-container"])
    elif sys.argv[1:]:
        raise ValueError("Unsupported bootstrap arguments")
    else:
        os.execvp("python3", ["python3", "/app/agent_runner.py", "--prompt-file", "/app/prompt.txt"])


if __name__ == "__main__":
    main()
