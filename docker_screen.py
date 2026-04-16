#!/usr/bin/env python3
"""Docker containers data collection and rendering."""

import subprocess
import time
from datetime import datetime

from PIL import ImageDraw

from shared import (
    BORDER,
    CYAN,
    FONT_DATA,
    FONT_SMALL,
    FONT_TINY,
    GREEN,
    GREEN_DIM,
    ORANGE,
    PURPLE,
    PURPLE_DIM,
    RED,
    WHITE_DIM,
    W,
    H,
    draw_corners,
    new_frame,
)


def get_docker_containers():
    try:
        output = subprocess.check_output(
            ["docker", "ps", "--format", "{{.Names}}|{{.Status}}|{{.Ports}}"],
            text=True,
            timeout=4
        )
    except Exception:
        return []

    containers = []
    for line in output.splitlines():
        if "|" not in line:
            continue
        parts = line.split("|")
        name = parts[0].strip()
        status = parts[1].strip() if len(parts) > 1 else ""
        ports = parts[2].strip() if len(parts) > 2 else ""

        health = get_container_health(name)
        running = "Up" in status

        containers.append({
            "name": name,
            "status": status,
            "ports": ports,
            "health": health,
            "running": running,
        })
    return containers


def get_container_health(container_name):
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=2
        )
        health = result.stdout.strip()
        if health in ("healthy", "unhealthy", "starting"):
            return health
    except Exception:
        pass
    return None


def get_container_uptime(container_name):
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.StartedAt}}", container_name],
            capture_output=True,
            text=True,
            timeout=2
        )
        started_at = result.stdout.strip()
        if started_at:
            from datetime import datetime
            started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            uptime = datetime.now().astimezone() - started
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            return f"{hours}h {minutes}m"
    except Exception:
        pass
    return "-"


class DockerScreen:
    def __init__(self):
        self.containers = []
        self.last_fetch = 0

    def render(self):
        now = time.time()
        if now - self.last_fetch > 5:
            self.containers = get_docker_containers()
            self.last_fetch = now
        return render_docker_frame(self.containers)


def render_docker_frame(containers):
    img = new_frame()
    draw = ImageDraw.Draw(img)

    draw.rectangle([8, 6, W - 9, 8], fill=PURPLE)
    draw.text((10, 10), "DOCKER CONTAINERS", fill=PURPLE, font=FONT_DATA)
    draw.text((10, 14), f"{len(containers)} running", fill=GREEN, font=FONT_TINY)
    draw.rectangle([8, 34, W - 9, 35], fill=PURPLE_DIM)

    start_y = 44
    row_h = 16
    max_rows = int((H - 26 - start_y - 10) / row_h)

    draw.rectangle([8, start_y, W - 9, H - 26], outline=BORDER, width=1)
    draw.text((12, start_y + 4), "CONTAINER", fill=WHITE_DIM, font=FONT_SMALL)
    draw.text((200, start_y + 4), "HEALTH", fill=WHITE_DIM, font=FONT_SMALL)
    draw.text((280, start_y + 4), "PORTS", fill=WHITE_DIM, font=FONT_SMALL)

    y = start_y + 20
    for i, container in enumerate(containers[:max_rows]):
        name = container["name"][:25]
        health = container["health"] or "native"
        ports = container["ports"][:20] if container["ports"] else "-"

        if not container["running"]:
            color = RED
        elif health == "healthy":
            color = GREEN
        elif health == "unhealthy":
            color = RED
        elif health == "starting":
            color = ORANGE
        else:
            color = CYAN

        draw.text((12, y), name, fill=WHITE_DIM, font=FONT_SMALL)
        draw.text((200, y), health.upper(), fill=color, font=FONT_SMALL)
        draw.text((280, y), ports, fill=CYAN, font=FONT_TINY)

        y += row_h

    overflow = len(containers) - max_rows
    if overflow > 0:
        draw.text((12, H - 36), f"+ {overflow} containers hidden", fill=WHITE_DIM, font=FONT_TINY)

    draw.text((12, H - 20), datetime.now().strftime("%H:%M:%S"), fill=GREEN_DIM, font=FONT_TINY)
    draw_corners(draw)
    return img
