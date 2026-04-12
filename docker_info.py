#!/usr/bin/env python3
"""Docker port parsing and monitor-to-container resolution helpers."""

import json
import re
import subprocess
import urllib.parse
from typing import Dict, Optional


def only_ports(value: str, prefer_public: bool = False) -> str:
    if not value:
        return ""
    ports = []
    seen = set()
    for item in value.split(","):
        text = item.strip()
        if not text:
            continue
        if "://" in text:
            parsed_url = urllib.parse.urlparse(text)
            if parsed_url.port:
                port = str(parsed_url.port)
                if port not in seen:
                    seen.add(port)
                    ports.append(port)
                continue
        if "->" in text:
            left, right = text.split("->", 1)
            text = left.strip() if prefer_public else right.strip()
        match = re.search(r":(\d{1,5})(?=$|/|,)", text)
        if not match:
            match = re.search(r"^(\d{1,5})(?:/(tcp|udp))?$", text)
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
        normalized = only_ports(ports.strip(), prefer_public=True)
        if not normalized:
            normalized = inspect_container_public_ports(name.strip())
        if not normalized:
            normalized = inspect_container_ports(name.strip())
        mapping[name.strip()] = normalized if normalized else "-"
    return mapping


def inspect_container_public_ports(container_name: str) -> str:
    try:
        raw = subprocess.check_output(
            ["docker", "inspect", "--format", "{{json .NetworkSettings.Ports}}", container_name],
            text=True,
            timeout=4,
        ).strip()
    except Exception:
        return ""
    if not raw or raw == "null":
        return ""
    try:
        parsed = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(parsed, dict):
        return ""
    ports = []
    seen = set()
    for bindings in parsed.values():
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            host_port = str(binding.get("HostPort", "")).strip()
            if host_port and host_port not in seen:
                seen.add(host_port)
                ports.append(host_port)
    return ",".join(ports)


def inspect_container_ports(container_name: str) -> str:
    try:
        raw = subprocess.check_output(
            ["docker", "inspect", "--format", "{{json .Config.ExposedPorts}}", container_name],
            text=True,
            timeout=4,
        ).strip()
    except Exception:
        return ""
    if not raw or raw == "null":
        return ""
    try:
        parsed = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(parsed, dict):
        return ""
    ports = []
    seen = set()
    for key in parsed.keys():
        port = only_ports(str(key))
        if not port:
            continue
        for item in port.split(","):
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                ports.append(item)
    return ",".join(ports)


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
    best_match = "-"
    best_score = -1
    for container, ports in docker_ports.items():
        normalized = _normalize_name(container)
        score = -1
        if target == normalized:
            score = 4
        elif target and (target in normalized or normalized in target):
            score = 3
        else:
            name_tokens = {token for token in re.split(r"[^a-z0-9]+", name.lower()) if len(token) >= 3}
            container_tokens = {token for token in re.split(r"[^a-z0-9]+", container.lower()) if len(token) >= 3}
            overlap = len(name_tokens & container_tokens)
            if overlap > 0:
                score = 1 + overlap
        if score > best_score:
            best_score = score
            best_match = ports
    return best_match if best_score > 0 else "-"
