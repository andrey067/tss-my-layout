#!/usr/bin/env python3
"""System resources data collection and rendering."""

import time
from collections import deque
from datetime import datetime

from PIL import ImageDraw

from shared import (
    BORDER,
    CYAN,
    FONT_BIG,
    FONT_DATA,
    FONT_SMALL,
    FONT_TINY,
    GREEN,
    GREEN_DIM,
    PURPLE,
    PURPLE_DIM,
    WHITE_DIM,
    W,
    H,
    draw_bar,
    draw_corners,
    draw_sparkline,
    new_frame,
    temp_color,
    usage_color,
)


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


class SystemResourceScreen:
    def __init__(self):
        self.net_hist = deque(maxlen=40)
        self.prev_total = None
        self.prev_ts = None

    def render(self):
        stats = get_local_stats()
        now = time.time()
        total = stats.get("net_sent", 0) + stats.get("net_recv", 0)
        if self.prev_total is not None and self.prev_ts is not None:
            delta = now - self.prev_ts
            if delta > 0:
                self.net_hist.append(max(0.0, (total - self.prev_total) / 1048576 / delta))
        self.prev_total = total
        self.prev_ts = now
        return render_resources_frame(stats, self.net_hist)


def render_resources_frame(stats, net_hist):
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
