#!/usr/bin/env python3
"""Docker port parsing and monitor-to-container resolution helpers."""

import re
import subprocess
from typing import Dict, Optional


def only_ports(value: str) -> str:
    if not value:
        return ""
    ports = []
    seen = set()
    for item in value.split(","):
        text = item.strip()
        if not text:
            continue
        if "->" in text:
            text = text.split("->", 1)[1].strip()
        match = re.search(r":(\d{1,5})(?:/(tcp|udp))?$", text)
        if not match:
            match = re.search(r"\b(\d{1,5})(?:/(tcp|udp))?\b", text)
        if not match:
            continue
        port = match.group(1)
        if port not in seen:
            seen.add(port)
            ports.append(port)
    return ",".join(ports)


def docker_ports_map(show_docker_ports: bool = True, docker_ps_output: Optional[str] = None) -> Dict[str, str]:
    if not show_docker_ports:
        return {}
    try:
        output = (
            docker_ps_output
            if docker_ps_output is not None
            else subprocess.check_output(["docker", "ps", "--format", "{{.Names}}|{{.Ports}}"], text=True, timeout=4)
        )
    except Exception:
        return {}

    mapping = {}
    for line in output.splitlines():
        if "|" not in line:
            continue
        name, ports = line.split("|", 1)
        normalized = only_ports(ports.strip())
        mapping[name.strip()] = normalized if normalized else "-"
    return mapping


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def resolve_port(name: str, monitor_port: str, docker_ports: Dict[str, str]) -> str:
    candidate = (monitor_port or "").strip()
    if candidate and candidate.lower() != "null":
        parsed = only_ports(candidate)
        return parsed if parsed else candidate
    if name in docker_ports:
        return docker_ports[name]
    lower = {k.lower(): v for k, v in docker_ports.items()}
    if name.lower() in lower:
        return lower[name.lower()]
    target = _normalize_name(name)
    for container, ports in docker_ports.items():
        normalized = _normalize_name(container)
        if target == normalized or target in normalized or normalized in target:
            return ports
    return "-"
