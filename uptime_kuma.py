#!/usr/bin/env python3
"""Uptime Kuma fetch/cache/render logic."""

import json
import re
import time
from datetime import datetime

import socketio

from PIL import ImageDraw

from docker_info import docker_ports_map, only_ports, resolve_port
from shared import (
    BG_PANEL,
    BORDER,
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
        hide_no_port_rows=True,
    ):
        self.kuma_enabled = kuma_enabled
        self.kuma_url = kuma_url.rstrip("/")
        self.kuma_token = kuma_token
        self.kuma_timeout = kuma_timeout
        self.kuma_poll_interval = kuma_poll_interval
        self.kuma_verify_ssl = kuma_verify_ssl
        self.kuma_max_rows = kuma_max_rows
        self.show_docker_ports = show_docker_ports
        self.hide_no_port_rows = hide_no_port_rows
        self.cache = {
            "summary": {"up": 0, "down": 0, "paused": 0, "unknown": 0, "total": 0},
            "monitors": [],
            "error": "",
            "source": "",
            "updated_at": "Never",
            "last_fetch": 0.0,
        }
        self._sio = None
        self._monitors_data = []
        self._info_data = {}

    def _monitor_port_hint(self, row):
        direct_candidates = [
            row.get("port"),
            row.get("monitor_port"),
            row.get("docker_port"),
            row.get("publicPort"),
            row.get("hostPort"),
        ]
        for value in direct_candidates:
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.lower() == "null":
                continue
            parsed = only_ports(text)
            if parsed:
                return parsed

        for field in ("url", "hostname"):
            value = row.get(field)
            if not value:
                continue
            parsed = only_ports(str(value).strip())
            if parsed:
                return parsed
        return ""

    def _normalize_name(self, value):
        return re.sub(r"[^a-z0-9]+", "", str(value).lower())

    def _name_tokens(self, value):
        return {token for token in re.split(r"[^a-z0-9]+", str(value).lower()) if len(token) >= 3}

    def _match_score(self, monitor_name, container_name):
        mn = self._normalize_name(monitor_name)
        cn = self._normalize_name(container_name)
        if not mn or not cn:
            return 0
        if mn == cn:
            return 100
        monitor_tokens = self._name_tokens(monitor_name)
        container_tokens = self._name_tokens(container_name)
        overlap = len(monitor_tokens & container_tokens)
        if overlap:
            return overlap * 10
        if len(mn) >= 6 and (mn.startswith(cn) or cn.startswith(mn)):
            return 5
        return 0

    def _best_container_match(self, monitor_name, docker_ports):
        best_name = None
        best_score = 0
        for container_name in docker_ports.keys():
            score = self._match_score(monitor_name, container_name)
            if score > best_score:
                best_score = score
                best_name = container_name
        return best_name if best_score > 0 else None

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

    def _fetch_kuma_payload(self):
        import threading

        monitors_data = []
        heartbeat_data = []

        def do_login(sio):
            time.sleep(0.3)
            if self.kuma_token:
                sio.emit("login", {
                    "username": "admin",
                    "password": self.kuma_token
                })

        try:
            sio = socketio.Client(reconnection=False, ssl_verify=self.kuma_verify_ssl)

            @sio.on("connect")
            def on_connect():
                threading.Thread(target=do_login, args=(sio,)).start()

            @sio.on("monitorList")
            def on_monitor_list(data):
                nonlocal monitors_data
                if isinstance(data, dict):
                    monitors_data = data

            @sio.on("heartbeat")
            def on_heartbeat(data):
                if isinstance(data, dict):
                    heartbeat_data.append(data)

            sio.connect(self.kuma_url, transports=["polling"], wait_timeout=self.kuma_timeout)

            start = time.time()
            while time.time() - start < self.kuma_timeout:
                if monitors_data:
                    break
                time.sleep(0.1)

        except Exception as exc:
            raise RuntimeError(f"Socket.IO error: {exc}")
        finally:
            try:
                sio.disconnect()
            except Exception:
                pass

        if monitors_data:
            hb_map = {h.get("monitorID"): h for h in heartbeat_data if isinstance(h, dict)}
            for mid, m in monitors_data.items():
                if mid in hb_map:
                    m["heartbeat"] = hb_map[mid]
            return self.kuma_url, {"monitors": list(monitors_data.values())}
        return self.kuma_url, {"monitors": []}

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
        monitor_rows = []

        for row in monitors:
            name = str(row.get("name") or row.get("friendly_name") or row.get("monitor_name") or row.get("id") or "unnamed")
            status = self._status_label(row.get("status", row.get("up", row.get("active", row.get("isUp")))))
            port_hint = self._monitor_port_hint(row)
            port = resolve_port(name, port_hint, docker_ports)
            if status == "UP":
                summary["up"] += 1
            elif status == "DOWN":
                summary["down"] += 1
            elif status == "PAUSED":
                summary["paused"] += 1
            else:
                summary["unknown"] += 1
            monitor_rows.append({"name": name, "status": status, "port": port})

        # Build final rows from Docker first (containers + public ports), using Kuma status when matched.
        used_containers = set()
        unmatched_monitor_rows = []
        for monitor_row in monitor_rows:
            matched_container = self._best_container_match(monitor_row["name"], docker_ports)
            if not matched_container:
                unmatched_monitor_rows.append(monitor_row)
                continue
            container_port = docker_ports.get(matched_container, "-")
            if container_port == "-":
                unmatched_monitor_rows.append(monitor_row)
                continue
            if matched_container in used_containers:
                unmatched_monitor_rows.append(monitor_row)
                continue
            used_containers.add(matched_container)
            rows.append({"name": matched_container, "status": monitor_row["status"], "port": container_port})

        # Add docker containers that were not in Kuma monitor list, keeping status UNKNOWN.
        for container_name, container_port in sorted(docker_ports.items()):
            if container_port == "-":
                continue
            if container_name in used_containers:
                continue
            rows.append({"name": container_name, "status": "UNKNOWN", "port": container_port})

        # Keep non-docker or URL-based Kuma monitors as fallback rows.
        for monitor_row in unmatched_monitor_rows:
            rows.append(monitor_row)

        self.cache["summary"] = summary
        self.cache["monitors"] = rows
        self.cache["error"] = ""
        self.cache["source"] = source
        self.cache["updated_at"] = datetime.now().strftime("%H:%M:%S")

    def render(self):
        self.refresh_cache()
        summary = self.cache["summary"]
        monitors = self.cache["monitors"]
        if self.hide_no_port_rows:
            monitors = [row for row in monitors if str(row.get("port", "")).strip() not in {"", "-"}]
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
        draw.text((402, start_y + 6), "STATE", fill=WHITE_DIM, font=FONT_SMALL)

        max_rows = min(self.kuma_max_rows, int((H - 26 - (start_y + 22)) / row_h))
        for idx, monitor in enumerate(monitors[:max_rows], start=0):
            y = start_y + 22 + idx * row_h
            status = monitor["status"]
            color = GREEN if status == "UP" else RED if status == "DOWN" else ORANGE
            draw.text((16, y), monitor["name"][:46], fill=WHITE_DIM, font=FONT_SMALL)
            draw.text((402, y), status, fill=color, font=FONT_SMALL)

        overflow = len(monitors) - max_rows
        if overflow > 0:
            draw.text((16, H - 36), f"+ {overflow} services hidden", fill=WHITE_DIM, font=FONT_TINY)

        draw_corners(draw)
        return img
