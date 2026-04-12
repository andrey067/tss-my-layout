#!/usr/bin/env python3
"""Screen runtime orchestration."""

import os
import time

from serial import SerialException

from layout import render_calibration_frame, render_orientation_frame
from shared import Screen, ScreenLockError
from system_resource import SystemResourceScreen
from uptime_kuma import UptimeKumaScreen


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


def _env_bool(name, default):
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _new_screen():
    while True:
        try:
            return Screen()
        except ScreenLockError as exc:
            raise SystemExit(str(exc))
        except Exception as exc:
            print(f"Screen init failed: {exc}. Retrying in 2s...")
            time.sleep(2)


def _current_mode(start_time, windows):
    if not windows:
        return "RESOURCES"
    total_seconds = sum(seconds for _, seconds in windows)
    elapsed = (time.monotonic() - start_time) % total_seconds
    cursor = 0
    for name, seconds in windows:
        cursor += seconds
        if elapsed < cursor:
            return name
    return windows[0][0]


def run_dashboard():
    _load_env_file()

    refresh_interval = max(0.5, float(os.getenv("REFRESH_INTERVAL", "1")))
    resources_seconds = max(5, int(os.getenv("RESOURCES_SCREEN_SECONDS", "30")))
    kuma_seconds = max(5, int(os.getenv("KUMA_SCREEN_SECONDS", "30")))

    kuma_enabled = _env_bool("KUMA_ENABLED", True)
    kuma_url = os.getenv("KUMA_URL", "http://127.0.0.1:3002").strip()
    kuma_token = os.getenv("KUMA_TOKEN", "").strip()
    kuma_timeout = max(1, int(os.getenv("KUMA_TIMEOUT", "8")))
    kuma_poll_interval = max(3, int(os.getenv("KUMA_POLL_INTERVAL", "10")))
    kuma_verify_ssl = _env_bool("KUMA_VERIFY_SSL", True)
    kuma_max_rows = max(4, int(os.getenv("KUMA_MAX_ROWS", "18")))
    show_docker_ports = _env_bool("SHOW_DOCKER_PORTS", True)

    calibration_mode = _env_bool("CALIBRATION_MODE", False)
    orientation_mode = _env_bool("ORIENTATION_MODE", False)

    resource_screen = SystemResourceScreen()
    kuma_screen = UptimeKumaScreen(
        kuma_enabled=kuma_enabled,
        kuma_url=kuma_url,
        kuma_token=kuma_token,
        kuma_timeout=kuma_timeout,
        kuma_poll_interval=kuma_poll_interval,
        kuma_verify_ssl=kuma_verify_ssl,
        kuma_max_rows=kuma_max_rows,
        show_docker_ports=show_docker_ports,
    )

    windows = [("RESOURCES", resources_seconds)]
    if kuma_enabled:
        windows.append(("KUMA", kuma_seconds))

    screen = _new_screen()
    start_time = time.monotonic()

    while True:
        if orientation_mode:
            frame = render_orientation_frame()
        elif calibration_mode:
            frame = render_calibration_frame()
        else:
            mode = _current_mode(start_time, windows)
            frame = resource_screen.render() if mode == "RESOURCES" else kuma_screen.render()

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

        time.sleep(refresh_interval)
