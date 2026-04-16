#!/usr/bin/env python3
"""Docker containers data collection and rendering."""

import time
from datetime import datetime

import docker
from PIL import ImageDraw

from shared import (
    BORDER,
    CYAN,
    FONT_DATA,
    FONT_SMALL,
    FONT_TINY,
    GREEN,
    GREEN_DIM,
    PURPLE,
    PURPLE_DIM,
    RED,
    WHITE_DIM,
    W,
    H,
    draw_corners,
    new_frame,
)


def _status_label(raw_status):
    return "RUNNING" if (raw_status or "").strip().lower() == "running" else "STOP"


def _public_port(ports):
    if not isinstance(ports, list):
        return "-"
    collected = []
    for entry in ports:
        if not isinstance(entry, dict):
            continue
        public_port = entry.get("PublicPort")
        if public_port is None:
            continue
        try:
            collected.append(int(public_port))
        except (TypeError, ValueError):
            continue
    if not collected:
        return "-"
    return str(min(collected))


def get_docker_containers():
    client = None
    try:
        client = docker.from_env()
        items = client.api.containers(all=True)
    except Exception:
        return []
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    containers = []
    for item in items:
        raw_status = str(item.get("State", "")).strip().lower()
        status_label = _status_label(raw_status)
        names = item.get("Names") or []
        if names and isinstance(names[0], str):
            name = names[0].lstrip("/")
        else:
            name = item.get("Id", "")[:12]
        containers.append(
            {
                "name": name,
                "status": status_label,
                "port": _public_port(item.get("Ports") or []),
                "running": status_label == "RUNNING",
            }
        )
    return containers


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
    running_count = sum(1 for container in containers if container.get("running"))

    draw.rectangle([8, 6, W - 9, 8], fill=PURPLE)
    draw.text((10, 10), "DOCKER CONTAINERS", fill=PURPLE, font=FONT_DATA)
    draw.text(
        (10, 14),
        f"{running_count} running / {len(containers)} total",
        fill=GREEN,
        font=FONT_TINY,
    )
    draw.rectangle([8, 34, W - 9, 35], fill=PURPLE_DIM)

    start_y = 44
    row_h = 16
    max_rows = int((H - 26 - start_y - 10) / row_h)

    draw.rectangle([8, start_y, W - 9, H - 26], outline=BORDER, width=1)
    draw.text((12, start_y + 4), "CONTAINER", fill=WHITE_DIM, font=FONT_SMALL)
    draw.text((200, start_y + 4), "STATUS", fill=WHITE_DIM, font=FONT_SMALL)
    draw.text((280, start_y + 4), "PORT", fill=WHITE_DIM, font=FONT_SMALL)

    y = start_y + 20
    for i, container in enumerate(containers[:max_rows]):
        name = container["name"][:25]
        status_label = container.get("status", "STOP")
        port = container.get("port", "-")[:20]
        color = GREEN if status_label == "RUNNING" else RED

        draw.text((12, y), name, fill=WHITE_DIM, font=FONT_SMALL)
        draw.text((200, y), status_label, fill=color, font=FONT_SMALL)
        draw.text((280, y), port, fill=CYAN, font=FONT_TINY)

        y += row_h

    overflow = len(containers) - max_rows
    if overflow > 0:
        draw.text(
            (12, H - 36),
            f"+ {overflow} containers hidden",
            fill=WHITE_DIM,
            font=FONT_TINY,
        )

    draw.text(
        (12, H - 20),
        datetime.now().strftime("%H:%M:%S"),
        fill=GREEN_DIM,
        font=FONT_TINY,
    )
    draw_corners(draw)
    return img
