#!/usr/bin/env python3
"""Entry-point for dashboard runtime."""

import os
import signal
import subprocess
import time

from shared import find_serial_port
from screen import run_dashboard


def _kill_usb_port_processes():
    port = find_serial_port()
    if not port:
        return

    try:
        result = subprocess.run(
            ["lsof", "-t", port],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return

    pids = {
        int(pid.strip())
        for pid in result.stdout.splitlines()
        if pid.strip().isdigit()
    }
    pids.discard(os.getpid())
    if not pids:
        return

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    deadline = time.time() + 1.5
    while time.time() < deadline:
        alive = []
        for pid in pids:
            try:
                os.kill(pid, 0)
                alive.append(pid)
            except OSError:
                pass
        if not alive:
            return
        time.sleep(0.1)

    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def main():
    _kill_usb_port_processes()
    run_dashboard()


if __name__ == "__main__":
    main()
