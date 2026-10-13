#!/usr/bin/env python3
"""Health check for the Infrastructure Automation Lab.

Reads hosts from the Ansible inventory and verifies that each server is in the
expected state: reachable over SSH, required services running, HTTP health
endpoint responding and unexpected ports closed.

Exit codes: 0 = all checks passed, 1 = at least one check failed,
2 = the inventory could not be loaded.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass

# What to check for each inventory group
GROUP_CHECKS: dict[str, dict] = {
    "lab_nodes": {"services": ["ssh", "ufw"], "closed_ports": [8080]},
    "webservers": {"services": ["nginx"], "http_health": True},
    "docker_hosts": {"services": ["docker"], "closed_ports": [80]},
}

SSH_USER = "ansible"
TIMEOUT = 5


@dataclass
class CheckResult:
    host: str
    check: str
    passed: bool
    detail: str


# --- Inventory -----------------------------------------------------------


def load_inventory() -> dict[str, dict]:
    """Run ansible-inventory and return the parsed hosts."""
    output = subprocess.run(
        ["ansible-inventory", "--list"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return parse_inventory(json.loads(output))


def parse_inventory(data: dict) -> dict[str, dict]:
    """Convert ansible-inventory JSON to {host: {"address": ..., "groups": [...]}}."""
    hostvars = data.get("_meta", {}).get("hostvars", {})
    hosts: dict[str, dict] = {}
    for group, content in data.items():
        if group == "_meta" or not isinstance(content, dict):
            continue
        for host in content.get("hosts", []):
            entry = hosts.setdefault(
                host,
                {
                    "address": hostvars.get(host, {}).get("ansible_host", host),
                    "groups": [],
                },
            )
            entry["groups"].append(group)
    return hosts


def expected_checks(groups: list[str]) -> dict:
    """Merge the checks of all groups a host belongs to."""
    services: set[str] = set()
    closed_ports: set[int] = set()
    http_health = False
    for group in groups:
        config = GROUP_CHECKS.get(group, {})
        services.update(config.get("services", []))
        closed_ports.update(config.get("closed_ports", []))
        http_health = http_health or config.get("http_health", False)
    return {
        "services": sorted(services),
        "closed_ports": sorted(closed_ports),
        "http_health": http_health,
    }


# --- Individual checks ---------------------------------------------------


def is_port_open(address: str, port: int) -> bool:
    """Try a TCP connection to the port."""
    try:
        with socket.create_connection((address, port), timeout=TIMEOUT):
            return True
    except OSError:
        return False


def check_service(address: str, service: str) -> tuple[bool, str]:
    """Check over SSH whether a systemd service is active."""
    command = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={TIMEOUT}",
        f"{SSH_USER}@{address}",
        "systemctl", "is-active", service,
    ]  # fmt: skip
    result = subprocess.run(command, capture_output=True, text=True)
    state = result.stdout.strip() or result.stderr.strip() or "unknown"
    return result.returncode == 0, state


def check_http_health(address: str) -> tuple[bool, str]:
    """Request /health and expect HTTP 200 with body 'ok'."""
    url = f"http://{address}/health"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            body = response.read().decode().strip()
            return response.status == 200 and body == "ok", f"HTTP {response.status} '{body}'"
    except (urllib.error.URLError, OSError) as error:
        return False, str(error)


# --- Orchestration -------------------------------------------------------


def check_host(host: str, address: str, groups: list[str]) -> list[CheckResult]:
    results = []

    ssh_open = is_port_open(address, 22)
    results.append(CheckResult(host, "ssh port 22", ssh_open, "open" if ssh_open else "closed"))
    if not ssh_open:
        return results  # no point in checking services without SSH

    checks = expected_checks(groups)

    for service in checks["services"]:
        passed, state = check_service(address, service)
        results.append(CheckResult(host, f"service {service}", passed, state))

    if checks["http_health"]:
        passed, detail = check_http_health(address)
        results.append(CheckResult(host, "http /health", passed, detail))

    for port in checks["closed_ports"]:
        is_open = is_port_open(address, port)
        detail = "OPEN (unexpected)" if is_open else "closed"
        results.append(CheckResult(host, f"port {port} closed", not is_open, detail))

    return results


def exit_code(results: list[CheckResult]) -> int:
    return 0 if all(result.passed for result in results) else 1


def print_report(results: list[CheckResult]) -> None:
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.host:<8} {result.check:<20} {result.detail}")
    failed = sum(not result.passed for result in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Health check for lab servers.")
    parser.add_argument("--json", action="store_true", help="output results as JSON")
    args = parser.parse_args()

    try:
        hosts = load_inventory()
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Could not load Ansible inventory: {error}", file=sys.stderr)
        return 2

    results: list[CheckResult] = []
    for host, info in sorted(hosts.items()):
        results.extend(check_host(host, info["address"], info["groups"]))

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print_report(results)

    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
