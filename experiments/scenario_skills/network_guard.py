"""Native Docker network guard for an emulated target, with fail-closed setup."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path


def firewall_rules(gateway, ports):
    gateway = str(ipaddress.IPv4Address(gateway))
    ports = [str(int(port)) for port in ports]
    if len(ports) != 2 or any(not 1 <= int(port) <= 65535 for port in ports):
        raise ValueError("Guard requires fixture and proxy ports")
    return [["-P", "OUTPUT", "DROP"], ["-F", "OUTPUT"],
            ["-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"]] + [
                ["-A", "OUTPUT", "-p", "tcp", "-d", gateway, "--dport", port, "-j", "ACCEPT"] for port in ports]


def guard_main():
    gateway = socket.gethostbyname("host.docker.internal")
    ports = [os.environ["BENCHMARK_FIXTURE_PORT"], os.environ["BENCHMARK_PROXY_PORT"]]
    env = dict(os.environ, XTABLES_LOCKFILE="/tmp/benchmark-xtables.lock")
    # Set policy before flushing; never create a temporary open network.
    subprocess.run(["ip6tables", "-P", "OUTPUT", "DROP"], check=True, env=env)
    for rule in firewall_rules(gateway, ports):
        subprocess.run(["iptables"] + rule, check=True, env=env)
    proof = {"type": "network_guard_ready", "gateway": gateway, "ports": [int(p) for p in ports],
             "ipv4": subprocess.check_output(["iptables", "-S", "OUTPUT"], text=True, env=env),
             "ipv6": subprocess.check_output(["ip6tables", "-S", "OUTPUT"], text=True, env=env)}
    print(json.dumps(proof), flush=True)
    while True:
        time.sleep(30)


def validate_proof(proof, fixture_port, proxy_port):
    gateway = str(ipaddress.IPv4Address(proof["gateway"]))
    if proof.get("type") != "network_guard_ready" or proof.get("ports") != [int(fixture_port), int(proxy_port)]:
        raise ValueError("Network guard proof does not match the task ports")
    expected = ["-P OUTPUT DROP", "-A OUTPUT -o lo -j ACCEPT"] + [
        "-A OUTPUT -d %s/32 -p tcp -m tcp --dport %d -j ACCEPT" % (gateway, port) for port in proof["ports"]]
    if proof.get("ipv4", "").splitlines() != expected or proof.get("ipv6", "").splitlines() != ["-P OUTPUT DROP"]:
        raise ValueError("Network guard contains unexpected firewall rules")
    return gateway


class NetworkGuard:
    """Start/verify guard before launching a target; remove it on every exit."""
    def __init__(self, image, fixture_port, proxy_port, directory):
        from .common import digest
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError("Network guard image must be an immutable local image ID")
        self.image, self.ports, self.directory = image, [fixture_port, proxy_port], Path(directory)
        self.name = "cekura-network-guard-" + digest(str(directory))[:16]

    def __enter__(self):
        from .common import ROOT, write
        self.directory.mkdir()
        command = ["docker", "run", "-d", "--pull=never", "--name", self.name, "--cap-drop=ALL",
                   "--cap-add=NET_ADMIN", "--cap-add=NET_RAW", "--security-opt=no-new-privileges", "--read-only",
                   "--tmpfs", "/tmp:rw,nosuid,size=16m", "--add-host=host.docker.internal:host-gateway",
                   "-v", str(ROOT / "network_guard.py") + ":/benchmark/network_guard.py:ro",
                   "-e", "BENCHMARK_FIXTURE_PORT=" + str(self.ports[0]),
                   "-e", "BENCHMARK_PROXY_PORT=" + str(self.ports[1]),
                   "--entrypoint", "python3", self.image, "/benchmark/network_guard.py"]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                logs = subprocess.run(["docker", "logs", self.name], check=True, capture_output=True, text=True, timeout=5)
                for line in logs.stdout.splitlines():
                    if line.startswith('{"type": "network_guard_ready"'):
                        proof = json.loads(line)
                        self.gateway = validate_proof(proof, *self.ports)
                        # Read rules independently instead of trusting a ready message.
                        for binary, field in (("iptables", "ipv4"), ("ip6tables", "ipv6")):
                            actual = subprocess.check_output(["docker", "exec", self.name, binary, "-S", "OUTPUT"], text=True, timeout=5)
                            if actual != proof[field]:
                                raise ValueError("Network guard rules changed during verification")
                        proof.update(image=self.image, container=self.name)
                        write(self.directory / "proof.json", proof)
                        (self.directory / "hosts").write_text("127.0.0.1 localhost\n%s host.docker.internal\n" % self.gateway)
                        for path in self.directory.iterdir():
                            path.chmod(0o644)
                        return self
                running = subprocess.check_output(["docker", "inspect", "--format", "{{.State.Running}}", self.name], text=True, timeout=5).strip()
                if running != "true":
                    raise RuntimeError("Native network guard setup failed: " + logs.stderr[-2000:])
                time.sleep(.1)
            raise RuntimeError("Native network guard setup timed out")
        except BaseException:
            self.__exit__()
            raise

    def target_args(self):
        from .common import ROOT
        return ["--network", "container:" + self.name,
                "-v", str(self.directory / "hosts") + ":/etc/hosts:ro",
                "-v", str(self.directory / "proof.json") + ":/benchmark/network-guard.json:ro",
                "-v", str(ROOT / "network_guard.py") + ":/benchmark/network_guard.py:ro",
                "-e", "BENCHMARK_NETWORK_GUARD_PROOF=/benchmark/network-guard.json"]

    def __exit__(self, *args):
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True, timeout=30)


if __name__ == "__main__":
    guard_main()
