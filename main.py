#!/usr/bin/env python3
"""Dual-screen runtime: resources (default landscape) + Uptime Kuma."""

import base64
import json
import os
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from PIL import ImageDraw
from serial import SerialException

from shared import (
    BG_PANEL,
    BORDER,
    CYAN,
    DISPLAY_MODE,
    FONT_BIG,
    FONT_DATA,
    FONT_MEGA,
    FONT_SMALL,
    FONT_TINY,
    GREEN,
    GREEN_DIM,
    ORANGE,
    PURPLE,
    PURPLE_DIM,
    RED,
    ScreenLockError,
    WHITE_DIM,
    W,
    H,
    Screen,
    draw_bar,
    draw_corners,
    draw_sparkline,
    new_frame,
    temp_color,
    usage_color,
)


def _load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


REFRESH_INTERVAL = max(0.5, float(os.getenv("REFRESH_INTERVAL", "1")))
RESOURCES_SCREEN_SECONDS = max(5, int(os.getenv("RESOURCES_SCREEN_SECONDS", "30")))
KUMA_SCREEN_SECONDS = max(5, int(os.getenv("KUMA_SCREEN_SECONDS", "30")))
KUMA_ENABLED = _env_bool("KUMA_ENABLED", True)
KUMA_URL = os.getenv("KUMA_URL", "http://127.0.0.1:3002").strip()
KUMA_TOKEN = os.getenv("KUMA_TOKEN", "").strip()
KUMA_TIMEOUT = max(1, int(os.getenv("KUMA_TIMEOUT", "8")))
KUMA_POLL_INTERVAL = max(3, int(os.getenv("KUMA_POLL_INTERVAL", "10")))
KUMA_VERIFY_SSL = _env_bool("KUMA_VERIFY_SSL", True)
KUMA_MAX_ROWS = max(4, int(os.getenv("KUMA_MAX_ROWS", "18")))
SHOW_DOCKER_PORTS = _env_bool("SHOW_DOCKER_PORTS", True)
CALIBRATION_MODE = _env_bool("CALIBRATION_MODE", False)

RESOURCE_WINDOW = [("RESOURCES", RESOURCES_SCREEN_SECONDS)]
WINDOWS = RESOURCE_WINDOW + ([("KUMA", KUMA_SCREEN_SECONDS)] if KUMA_ENABLED else [])
WINDOW_TOTAL_SECONDS = sum(seconds for _, seconds in WINDOWS)

_kuma_cache = {
    "summary": {"up": 0, "down": 0, "paused": 0, "unknown": 0, "total": 0},
    "monitors": [],
    "error": "",
    "source": "",
    "updated_at": "Never",
    "last_fetch": 0.0,
}


def get_local_stats():
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        temp = 0.0
        try:
            temps = psutil.sensors_temperatures()
            for name in ("coretemp", "cpu_thermal", "k10temp", "soc_dts0"):
                if name in temps and temps[name]:
                    temp = temps[name][0].current
                    break
            if temp == 0 and temps:
                temp = next(iter(temps.values()))[0].current
        except Exception:
            pass

        disk_pct = 0.0
        for mount in ("/DATA", "/"):
            try:
                disk_pct = psutil.disk_usage(mount).percent
                break
            except Exception:
                continue

        return {
            "cpu": cpu,
            "mem_pct": mem.percent,
            "temp": temp,
            "disk_pct": disk_pct,
            "net_sent": psutil.net_io_counters().bytes_sent,
            "net_recv": psutil.net_io_counters().bytes_recv,
            "uptime": time.time() - psutil.boot_time(),
        }
    except Exception:
        return {
            "cpu": 0,
            "mem_pct": 0,
            "temp": 0,
            "disk_pct": 0,
            "net_sent": 0,
            "net_recv": 0,
            "uptime": 0,
        }


def _kuma_candidate_urls(base_or_endpoint: str) -> List[str]:
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


def _kuma_requests() -> List[Tuple[Dict, Dict, Optional[Tuple[str, str]]]]:
    if not KUMA_TOKEN:
        return [({}, {}, None)]
    return [
        ({}, {}, ("", KUMA_TOKEN)),
        ({"Authorization": f"Api-Key {KUMA_TOKEN}"}, {}, None),
        ({"X-API-Key": KUMA_TOKEN}, {}, None),
        ({}, {"apikey": KUMA_TOKEN}, None),
        ({}, {"api_key": KUMA_TOKEN}, None),
    ]


def _status_label(raw_status) -> str:
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


def _extract_monitors(payload) -> List[Dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("monitors", "data", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_monitors(value)
            if nested:
                return nested
    return []


def _parse_metrics_monitors(text: str) -> List[Dict]:
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


def _fetch_kuma_payload():
    last_error = None
    ssl_context = ssl.create_default_context() if KUMA_VERIFY_SSL else ssl._create_unverified_context()

    for candidate in _kuma_candidate_urls(KUMA_URL):
        for headers_extra, params_extra, basic_auth in _kuma_requests():
            try:
                params = urllib.parse.urlencode(params_extra)
                url = f"{candidate}?{params}" if params else candidate
                headers = {"Accept": "application/json", **headers_extra}
                if basic_auth is not None:
                    token = f"{basic_auth[0]}:{basic_auth[1]}".encode("utf-8")
                    headers["Authorization"] = f"Basic {base64.b64encode(token).decode('ascii')}"
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=KUMA_TIMEOUT, context=ssl_context) as response:
                    raw_bytes = response.read()
                    content_type = response.headers.get("Content-Type", "").lower()
                text = raw_bytes.decode("utf-8", errors="replace")
                if "json" in content_type or text.lstrip().startswith(("{", "[")):
                    return candidate, json.loads(text)
                monitors = _parse_metrics_monitors(text)
                if monitors:
                    return candidate, {"monitors": monitors}
                raise ValueError("Unsupported response format")
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
    raise RuntimeError(f"Could not fetch Kuma data from {KUMA_URL}: {last_error}")


def _docker_ports_map() -> Dict[str, str]:
    if not SHOW_DOCKER_PORTS:
        return {}
    try:
        output = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}|{{.Ports}}"], text=True, timeout=4)
    except Exception:
        return {}

    mapping = {}
    for line in output.splitlines():
        if "|" not in line:
            continue
        name, ports = line.split("|", 1)
        mapping[name.strip()] = ports.strip() if ports.strip() else "-"
    return mapping


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _resolve_port(name: str, monitor_port: str, docker_ports: Dict[str, str]) -> str:
    candidate = (monitor_port or "").strip()
    if candidate and candidate.lower() != "null":
        return candidate
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


def refresh_kuma_cache(force: bool = False):
    now = time.monotonic()
    if not force and now - _kuma_cache["last_fetch"] < KUMA_POLL_INTERVAL:
        return
    _kuma_cache["last_fetch"] = now

    if not KUMA_ENABLED:
        _kuma_cache["error"] = "KUMA_ENABLED=false"
        return
    if not KUMA_URL:
        _kuma_cache["error"] = "Set KUMA_URL"
        return

    try:
        source, payload = _fetch_kuma_payload()
    except Exception as exc:
        _kuma_cache["error"] = f"Kuma API error: {exc}"
        _kuma_cache["updated_at"] = datetime.now().strftime("%H:%M:%S")
        return

    monitors = _extract_monitors(payload)
    docker_ports = _docker_ports_map()
    rows = []
    summary = {"up": 0, "down": 0, "paused": 0, "unknown": 0, "total": len(monitors)}

    for row in monitors:
        name = str(row.get("name") or row.get("friendly_name") or row.get("monitor_name") or row.get("id") or "unnamed")
        status = _status_label(row.get("status", row.get("up", row.get("active", row.get("isUp")))))
        port = _resolve_port(name, str(row.get("port") or row.get("monitor_port") or ""), docker_ports)
        if status == "UP":
            summary["up"] += 1
        elif status == "DOWN":
            summary["down"] += 1
        elif status == "PAUSED":
            summary["paused"] += 1
        else:
            summary["unknown"] += 1
        rows.append({"name": name, "status": status, "port": port})

    _kuma_cache["summary"] = summary
    _kuma_cache["monitors"] = rows
    _kuma_cache["error"] = ""
    _kuma_cache["source"] = source
    _kuma_cache["updated_at"] = datetime.now().strftime("%H:%M:%S")


def _current_mode(start_time: float) -> str:
    if not KUMA_ENABLED:
        return "RESOURCES"
    elapsed = (time.monotonic() - start_time) % WINDOW_TOTAL_SECONDS
    cursor = 0
    for name, seconds in WINDOWS:
        cursor += seconds
        if elapsed < cursor:
            return name
    return "RESOURCES"


def render_resources_frame(stats: Dict[str, float], net_hist: deque):
    img = new_frame()
    draw = ImageDraw.Draw(img)

    draw.rectangle([8, 6, W - 9, 8], fill=PURPLE)
    draw.text((10, 10), "RESOURCES", fill=PURPLE, font=FONT_BIG)
    draw.text((145, 14), "LANDSCAPE", fill=GREEN, font=FONT_TINY)
    draw.rectangle([8, 34, W - 9, 35], fill=PURPLE_DIM)

    x0, x1 = 8, W - 9
    y0, y1 = 44, H - 26
    draw.rectangle([x0, y0, x1, y1], outline=BORDER, width=1)

    cpu = float(stats.get("cpu", 0))
    mem = float(stats.get("mem_pct", 0))
    temp = float(stats.get("temp", 0))
    disk = float(stats.get("disk_pct", 0))

    draw.text((18, 58), "CPU", fill=WHITE_DIM, font=FONT_SMALL)
    draw.text((78, 52), f"{cpu:.0f}%", fill=usage_color(cpu), font=FONT_BIG)
    draw_bar(draw, 150, 60, 300, 10, cpu, usage_color(cpu))

    draw.text((18, 92), "MEM", fill=WHITE_DIM, font=FONT_SMALL)
    draw.text((78, 86), f"{mem:.0f}%", fill=usage_color(mem), font=FONT_BIG)
    draw_bar(draw, 150, 94, 300, 10, mem, usage_color(mem))

    draw.text((18, 126), "TEMP", fill=WHITE_DIM, font=FONT_SMALL)
    draw.text((74, 120), f"{temp:.0f}C", fill=temp_color(temp), font=FONT_BIG)
    draw_bar(draw, 150, 128, 300, 10, temp, temp_color(temp))

    draw.text((18, 160), "DISK", fill=WHITE_DIM, font=FONT_SMALL)
    draw.text((78, 154), f"{disk:.0f}%", fill=usage_color(disk), font=FONT_BIG)
    draw_bar(draw, 150, 162, 300, 10, disk, usage_color(disk))

    draw.text((18, 194), "NET", fill=WHITE_DIM, font=FONT_SMALL)
    current_speed = net_hist[-1] if net_hist else 0
    draw.text((72, 188), f"{current_speed:.1f} MB/s", fill=CYAN, font=FONT_DATA)
    draw_sparkline(draw, 150, 194, 300, 58, list(net_hist), CYAN)

    uptime_seconds = int(stats.get("uptime", 0))
    draw.text((18, 268), f"UP {uptime_seconds // 3600:02d}h {(uptime_seconds % 3600) // 60:02d}m", fill=GREEN_DIM, font=FONT_DATA)
    draw.text((350, 268), datetime.now().strftime("%H:%M:%S"), fill=GREEN_DIM, font=FONT_DATA)

    draw_corners(draw)
    return img


def render_kuma_frame():
    refresh_kuma_cache()
    summary = _kuma_cache["summary"]
    monitors = _kuma_cache["monitors"]
    error = _kuma_cache["error"]
    updated = _kuma_cache["updated_at"]

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

    max_rows = min(KUMA_MAX_ROWS, int((H - 26 - (start_y + 22)) / row_h))
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


def render_calibration_frame():
    img = new_frame()
    draw = ImageDraw.Draw(img)

    draw.rectangle([8, 6, W - 9, 8], fill=PURPLE)
    draw.text((10, 10), "DISPLAY CALIBRATION", fill=PURPLE, font=FONT_BIG)
    draw.rectangle([8, 34, W - 9, 35], fill=PURPLE_DIM)

    draw.rectangle([8, 44, W - 9, H - 26], outline=BORDER, width=2)
    draw.text((16, 52), "TOP-LEFT", fill=GREEN, font=FONT_SMALL)
    draw.text((W - 92, 52), "TOP-RIGHT", fill=GREEN, font=FONT_SMALL)
    draw.text((16, H - 46), "BOTTOM-LEFT", fill=GREEN, font=FONT_SMALL)
    draw.text((W - 114, H - 46), "BOTTOM-RIGHT", fill=GREEN, font=FONT_SMALL)

    draw.text((132, 114), "LEFT  ----->  RIGHT", fill=CYAN, font=FONT_DATA)
    draw.text((142, 150), "UP", fill=CYAN, font=FONT_DATA)
    draw.text((136, 172), "^", fill=CYAN, font=FONT_MEGA)
    draw.text((136, 216), "v", fill=CYAN, font=FONT_MEGA)
    draw.text((130, 256), "DOWN", fill=CYAN, font=FONT_DATA)

    draw.text((14, H - 18), f"MODE: {DISPLAY_MODE}", fill=WHITE_DIM, font=FONT_TINY)
    draw.text((W - 86, H - 18), datetime.now().strftime("%H:%M:%S"), fill=WHITE_DIM, font=FONT_TINY)
    draw_corners(draw)
    return img


def _new_screen():
    while True:
        try:
            return Screen()
        except ScreenLockError as exc:
            raise SystemExit(str(exc))
        except Exception as exc:
            print(f"Screen init failed: {exc}. Retrying in 2s...")
            time.sleep(2)


def main():
    screen = _new_screen()
    start_time = time.monotonic()

    net_hist = deque(maxlen=40)
    prev_total = None
    prev_ts = None

    while True:
        stats = get_local_stats()
        now = time.time()

        total = stats.get("net_sent", 0) + stats.get("net_recv", 0)
        if prev_total is not None and prev_ts is not None:
            delta = now - prev_ts
            if delta > 0:
                net_hist.append(max(0.0, (total - prev_total) / 1048576 / delta))
        prev_total = total
        prev_ts = now

        if CALIBRATION_MODE:
            frame = render_calibration_frame()
        else:
            frame = render_resources_frame(stats, net_hist) if _current_mode(start_time) == "RESOURCES" else render_kuma_frame()

        try:
            screen.show(frame)
        except SerialException as exc:
            print(f"Serial error: {exc}. Reconnecting screen...")
            try:
                screen.close()
            except Exception:
                pass
            screen = _new_screen()
        except Exception as exc:
            print(f"Render error: {exc}")

        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
