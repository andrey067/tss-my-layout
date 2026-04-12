#!/usr/bin/env python3
"""Uptime Kuma fetch/cache/render logic."""

import base64
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from PIL import ImageDraw

from docker_info import docker_ports_map, resolve_port
from shared import (
    BG_PANEL,
    BORDER,
    CYAN,
    FONT_BIG,
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


class UptimeKumaScreen:
    def __init__(
        self,
        kuma_enabled=True,
        kuma_url="http://127.0.0.1:3002",
        kuma_token="",
        kuma_timeout=8,
        kuma_poll_interval=10,
        kuma_verify_ssl=True,
        kuma_max_rows=18,
        show_docker_ports=True,
    ):
        self.kuma_enabled = kuma_enabled
        self.kuma_url = kuma_url
        self.kuma_token = kuma_token
        self.kuma_timeout = kuma_timeout
        self.kuma_poll_interval = kuma_poll_interval
        self.kuma_verify_ssl = kuma_verify_ssl
        self.kuma_max_rows = kuma_max_rows
        self.show_docker_ports = show_docker_ports
        self.cache = {
            "summary": {"up": 0, "down": 0, "paused": 0, "unknown": 0, "total": 0},
            "monitors": [],
            "error": "",
            "source": "",
            "updated_at": "Never",
            "last_fetch": 0.0,
        }

    def _kuma_candidate_urls(self, base_or_endpoint):
        parsed = urllib.parse.urlparse(base_or_endpoint)
        if parsed.scheme and parsed.netloc and parsed.path and parsed.path != "/":
            return [base_or_endpoint]
        base = base_or_endpoint.rstrip("/")
        return [
            f"{base}/metrics",
            f"{base}/api/monitors",
            f"{base}/api/monitor",
            f"{base}/api/status-page/monitor-list",
        ]

    def _kuma_requests(self):
        if not self.kuma_token:
            return [({}, {}, None)]
        return [
            ({}, {}, ("", self.kuma_token)),
            ({"Authorization": f"Api-Key {self.kuma_token}"}, {}, None),
            ({"X-API-Key": self.kuma_token}, {}, None),
            ({}, {"apikey": self.kuma_token}, None),
            ({}, {"api_key": self.kuma_token}, None),
        ]

    def _status_label(self, raw_status):
        if isinstance(raw_status, bool):
            return "UP" if raw_status else "DOWN"
        if isinstance(raw_status, (int, float)):
            value = int(raw_status)
            if value == 1:
                return "UP"
            if value == 0:
                return "DOWN"
            if value in (2, 3):
                return "PAUSED"
            return "UNKNOWN"
        if isinstance(raw_status, str):
            text = raw_status.strip().upper()
            if text in {"UP", "OK", "HEALTHY"}:
                return "UP"
            if text in {"DOWN", "FAIL", "UNHEALTHY"}:
                return "DOWN"
            if text in {"PAUSED", "MAINTENANCE"}:
                return "PAUSED"
        return "UNKNOWN"

    def _extract_monitors(self, payload):
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("monitors", "data", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = self._extract_monitors(value)
                if nested:
                    return nested
        return []

    def _parse_metrics_monitors(self, text):
        rows = []
        pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"\\])*)"')
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("monitor_status{") or "} " not in line:
                continue
            labels_block, value_raw = line.split("} ", 1)
            labels = labels_block[len("monitor_status{") :]
            parsed = {k: v.replace('\\"', '"') for k, v in pattern.findall(labels)}
            name = parsed.get("monitor_name", "")
            if not name:
                continue
            try:
                status_value = int(float(value_raw.strip()))
            except ValueError:
                status_value = -1
            rows.append(
                {
                    "name": name,
                    "status": status_value,
                    "monitor_type": parsed.get("monitor_type", "docker"),
                    "monitor_port": parsed.get("monitor_port", ""),
                }
            )
        return rows

    def _fetch_kuma_payload(self):
        last_error = None
        ssl_context = ssl.create_default_context() if self.kuma_verify_ssl else ssl._create_unverified_context()

        for candidate in self._kuma_candidate_urls(self.kuma_url):
            for headers_extra, params_extra, basic_auth in self._kuma_requests():
                try:
                    params = urllib.parse.urlencode(params_extra)
                    url = f"{candidate}?{params}" if params else candidate
                    headers = {"Accept": "application/json", **headers_extra}
                    if basic_auth is not None:
                        token = f"{basic_auth[0]}:{basic_auth[1]}".encode("utf-8")
                        headers["Authorization"] = f"Basic {base64.b64encode(token).decode('ascii')}"
                    request = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(request, timeout=self.kuma_timeout, context=ssl_context) as response:
                        raw_bytes = response.read()
                        content_type = response.headers.get("Content-Type", "").lower()
                    text = raw_bytes.decode("utf-8", errors="replace")
                    if "json" in content_type or text.lstrip().startswith(("{", "[")):
                        return candidate, json.loads(text)
                    monitors = self._parse_metrics_monitors(text)
                    if monitors:
                        return candidate, {"monitors": monitors}
                    raise ValueError("Unsupported response format")
                except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    last_error = exc
        raise RuntimeError(f"Could not fetch Kuma data from {self.kuma_url}: {last_error}")

    def refresh_cache(self, force=False):
        now = time.monotonic()
        if not force and now - self.cache["last_fetch"] < self.kuma_poll_interval:
            return
        self.cache["last_fetch"] = now

        if not self.kuma_enabled:
            self.cache["error"] = "KUMA_ENABLED=false"
            return
        if not self.kuma_url:
            self.cache["error"] = "Set KUMA_URL"
            return

        try:
            source, payload = self._fetch_kuma_payload()
        except Exception as exc:
            self.cache["error"] = f"Kuma API error: {exc}"
            self.cache["updated_at"] = datetime.now().strftime("%H:%M:%S")
            return

        monitors = self._extract_monitors(payload)
        docker_ports = docker_ports_map(self.show_docker_ports)
        rows = []
        summary = {"up": 0, "down": 0, "paused": 0, "unknown": 0, "total": len(monitors)}

        for row in monitors:
            name = str(row.get("name") or row.get("friendly_name") or row.get("monitor_name") or row.get("id") or "unnamed")
            status = self._status_label(row.get("status", row.get("up", row.get("active", row.get("isUp")))))
            port = resolve_port(name, str(row.get("port") or row.get("monitor_port") or ""), docker_ports)
            if status == "UP":
                summary["up"] += 1
            elif status == "DOWN":
                summary["down"] += 1
            elif status == "PAUSED":
                summary["paused"] += 1
            else:
                summary["unknown"] += 1
            rows.append({"name": name, "status": status, "port": port})

        self.cache["summary"] = summary
        self.cache["monitors"] = rows
        self.cache["error"] = ""
        self.cache["source"] = source
        self.cache["updated_at"] = datetime.now().strftime("%H:%M:%S")

    def render(self):
        self.refresh_cache()
        summary = self.cache["summary"]
        monitors = self.cache["monitors"]
        error = self.cache["error"]
        updated = self.cache["updated_at"]

        img = new_frame()
        draw = ImageDraw.Draw(img)

        draw.rectangle([8, 6, W - 9, 8], fill=PURPLE)
        draw.text((10, 10), "UPTIME KUMA", fill=PURPLE, font=FONT_BIG)
        draw.text((176, 14), "STATUS", fill=GREEN, font=FONT_TINY)
        draw.rectangle([8, 34, W - 9, 35], fill=PURPLE_DIM)

        draw.text((12, 44), f"TOTAL:{summary['total']} UP:{summary['up']} DOWN:{summary['down']} PAUSED:{summary['paused']}", fill=GREEN_DIM, font=FONT_SMALL)
        draw.text((12, 57), f"UPDATED: {updated}", fill=WHITE_DIM, font=FONT_TINY)

        if error:
            draw.rectangle([8, 78, W - 9, H - 26], fill=BG_PANEL, outline=BORDER, width=1)
            draw.text((16, 92), "KUMA API ERROR", fill=RED, font=FONT_DATA)
            draw.text((16, 112), error[:82], fill=WHITE_DIM, font=FONT_SMALL)
            draw_corners(draw)
            return img

        start_y = 78
        row_h = 13
        draw.rectangle([8, start_y, W - 9, H - 26], fill=BG_PANEL, outline=BORDER, width=1)
        draw.text((16, start_y + 6), "SERVICE", fill=WHITE_DIM, font=FONT_SMALL)
        draw.text((302, start_y + 6), "PORT", fill=WHITE_DIM, font=FONT_SMALL)
        draw.text((402, start_y + 6), "STATE", fill=WHITE_DIM, font=FONT_SMALL)

        max_rows = min(self.kuma_max_rows, int((H - 26 - (start_y + 22)) / row_h))
        for idx, monitor in enumerate(monitors[:max_rows], start=0):
            y = start_y + 22 + idx * row_h
            status = monitor["status"]
            color = GREEN if status == "UP" else RED if status == "DOWN" else ORANGE
            draw.text((16, y), monitor["name"][:34], fill=WHITE_DIM, font=FONT_SMALL)
            draw.text((302, y), str(monitor["port"])[:14], fill=CYAN, font=FONT_SMALL)
            draw.text((402, y), status, fill=color, font=FONT_SMALL)

        overflow = len(monitors) - max_rows
        if overflow > 0:
            draw.text((16, H - 36), f"+ {overflow} services hidden", fill=WHITE_DIM, font=FONT_TINY)

        draw_corners(draw)
        return img
