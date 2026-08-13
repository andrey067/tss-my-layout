#!/usr/bin/env python3
"""Screen runtime orchestration."""

import os
import time

from serial import SerialException

from layout import render_calibration_frame, render_orientation_frame
from shared import Screen, ScreenLockError, find_serial_port
from system_resource import SystemResourceScreen


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
    waiting_for_display = False
    while find_serial_port() is None:
        if not waiting_for_display:
            print("Display not connected. Waiting for USB monitor...")
            waiting_for_display = True
        time.sleep(2)
    if waiting_for_display:
        print("Display detected. Starting dashboards...")

    while True:
        try:
            return Screen()
        except ScreenLockError as exc:
            raise SystemExit(str(exc))
        except Exception as exc:
            print(f"Screen init failed: {exc}. Retrying in 2s...")
            time.sleep(2)


def run_dashboard():
    _load_env_file()

    refresh_interval = max(0.5, float(os.getenv("REFRESH_INTERVAL", "1")))

    calibration_mode = _env_bool("CALIBRATION_MODE", False)
    orientation_mode = _env_bool("ORIENTATION_MODE", False)

    resource_screen = SystemResourceScreen()

    screen = _new_screen()

    while True:
        if orientation_mode:
            frame = render_orientation_frame()
        elif calibration_mode:
            frame = render_calibration_frame()
        else:
            frame = resource_screen.render()

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
