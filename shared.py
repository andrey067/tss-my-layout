"""
Shared screen driver, palette, fonts, and drawing helpers for all Zima screens.
"""

import serial
import serial.tools.list_ports
import time
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

# ── Screen constants ───────────────────────────────────────────
# Canvas (what you see — landscape)
W, H = 480, 320
# Physical screen pixels (portrait native)
SCREEN_W, SCREEN_H = 320, 480
BAUD = 115200
DISPLAY_MODE = os.environ.get("DISPLAY_MODE", "landscape").strip().lower()

# ── Palette ────────────────────────────────────────────────────
BG           = (8, 2, 20)
BG_PANEL     = (14, 6, 32)
BORDER       = (40, 20, 80)
BORDER_HI    = (90, 45, 160)
GREEN        = (0, 255, 65)
GREEN_DIM    = (0, 140, 36)
GREEN_DARK   = (0, 60, 16)
PURPLE       = (140, 60, 220)
PURPLE_DIM   = (80, 35, 130)
ORANGE       = (255, 120, 0)
RED          = (255, 40, 40)
WHITE_DIM    = (140, 130, 160)
YELLOW       = (255, 230, 0)
CYAN         = (0, 220, 255)
GRAY         = (50, 40, 70)

# ── Font loading ───────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))

def load_font(size):
    candidates = [
        os.path.join(_script_dir, "JetBrainsMono.ttf"),
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        os.path.expanduser("~/Library/Fonts/JetBrainsMono[wght].ttf"),
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

FONT_HEADER = load_font(15)
FONT_TITLE  = load_font(11)
FONT_DATA   = load_font(11)
FONT_BIG    = load_font(22)
FONT_HUGE   = load_font(48)
FONT_SMALL  = load_font(9)
FONT_TINY   = load_font(8)
FONT_MED    = load_font(13)
FONT_MEGA   = load_font(36)

# ── Screen driver ──────────────────────────────────────────────
CMD_DISPLAY_BITMAP = 197
CMD_HELLO = 69
CMD_SET_BRIGHTNESS = 110


class ScreenLockError(RuntimeError):
    pass

def build_cmd(x, y, ex, ey, cmd):
    buf = bytearray(6)
    buf[0] = (x >> 2) & 0xFF
    buf[1] = (((x & 3) << 6) + (y >> 4)) & 0xFF
    buf[2] = (((y & 15) << 4) + (ex >> 6)) & 0xFF
    buf[3] = (((ex & 63) << 2) + (ey >> 8)) & 0xFF
    buf[4] = ey & 0xFF
    buf[5] = cmd
    return bytes(buf)

def find_serial_port():
    override = os.environ.get("SERIAL_PORT")
    if override:
        return override
    for p in serial.tools.list_ports.comports():
        if p.serial_number and "USB35INCH" in p.serial_number:
            return p.device
    for candidate in ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0"]:
        if os.path.exists(candidate):
            return candidate
    return None

class Screen:
    def __init__(self, port=None):
        self._lock_file = None
        self._acquire_instance_lock()

        port = port or find_serial_port()
        if not port:
            self._release_instance_lock()
            raise RuntimeError("USB monitor not found")
        self.ser = serial.Serial(port, BAUD, timeout=2, rtscts=True)
        time.sleep(0.1)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes([CMD_HELLO] * 6))
        self.ser.flush()
        time.sleep(0.5)
        self.ser.read(6)
        self.ser.reset_input_buffer()
        level = 255 - int(0.88 * 255)
        self.ser.write(build_cmd(level, 0, 0, 0, CMD_SET_BRIGHTNESS))
        self.ser.flush()

    def show(self, img):
        # Save preview for web UI (landscape, before rotation)
        try:
            preview_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "current_frame.png")
            img.save(preview_path)
        except Exception:
            pass
        # Rotate canvas to match selected orientation mode on physical display.
        if img.size == (W, H):
            rotations = {
                "landscape": -90,
                "reverse_landscape": 90,
                "portrait": -90,
                "reverse_portrait": 90,
            }
            angle = rotations.get(DISPLAY_MODE, 90)
            img = img.rotate(angle, expand=True)
        if img.size != (SCREEN_W, SCREEN_H):
            img = img.resize((SCREEN_W, SCREEN_H))
        img = img.convert("RGB")
        px = np.asarray(img).reshape(-1, 3).astype(np.uint16)
        rgb565 = ((px[:, 0] >> 3) << 11) | ((px[:, 1] >> 2) << 5) | (px[:, 2] >> 3)
        data = rgb565.astype('<u2').tobytes()
        self.ser.write(build_cmd(0, 0, SCREEN_W - 1, SCREEN_H - 1, CMD_DISPLAY_BITMAP))
        self.ser.flush()
        chunk = SCREEN_W * 8
        for i in range(0, len(data), chunk):
            self.ser.write(data[i:i + chunk])
            self.ser.flush()

    def close(self):
        try:
            self.ser.close()
        finally:
            self._release_instance_lock()

    def _acquire_instance_lock(self):
        lock_path = Path("/tmp/tss-my-layouts-serial.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = open(lock_path, "w", encoding="utf-8")
        if fcntl is None:
            return
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
        except OSError:
            raise ScreenLockError("Another dashboard instance is already running.")

    def _release_instance_lock(self):
        if not self._lock_file:
            return
        if fcntl is not None:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            self._lock_file.close()
        except OSError:
            pass
        self._lock_file = None

# ── Drawing helpers ────────────────────────────────────────────
def new_frame():
    """Create a new frame with background and scanlines."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    for sy in range(0, H, 3):
        draw.line([(0, sy), (W, sy)], fill=(255, 255, 255), width=1)
    bg_over = Image.new("RGB", (W, H), BG)
    img = Image.blend(img, bg_over, 0.92)
    return img

def draw_header(draw, title, subtitle=None):
    """Draw standard header with purple bar and title."""
    x1 = W - 9
    y = 8
    draw.rectangle([8, y, x1, y + 2], fill=PURPLE)
    y += 6
    draw.text((10, y), title, fill=PURPLE, font=FONT_BIG)
    if subtitle:
        tx = 10 + draw.textlength(title, font=FONT_BIG) + 10
        draw.text((tx, y + 4), subtitle, fill=GREEN, font=FONT_HEADER)
    y += 26
    draw.rectangle([8, y, x1, y + 1], fill=PURPLE_DIM)
    y += 4
    now = datetime.now()
    draw.text((10, y), f"▌{now.strftime('%H:%M:%S')}", fill=GREEN_DIM, font=FONT_TINY)
    draw.text((100, y), "◆ ONLINE", fill=GREEN, font=FONT_TINY)
    draw.text((170, y), f"▌{now.strftime('%Y-%m-%d')}", fill=GREEN_DIM, font=FONT_TINY)
    return y + 14  # next available y

def draw_footer(draw):
    """Draw standard footer with clock and heartbeat."""
    now = datetime.now()
    x1 = W - 9
    fy = H - 22
    draw.rectangle([8, fy, x1, fy + 1], fill=BORDER)
    fy += 5
    beat = "●" if now.second % 2 == 0 else "○"
    draw.text((10, fy), beat, fill=GREEN if now.second % 2 == 0 else GREEN_DARK, font=FONT_SMALL)
    draw.text((22, fy), now.strftime("%H:%M:%S"), fill=GREEN, font=FONT_DATA)
    draw.text((105, fy), now.strftime("%a %Y-%m-%d"), fill=PURPLE_DIM, font=FONT_DATA)

def draw_corners(draw):
    """Draw decorative corner accents."""
    for (cx, cy, col) in [(0, 0, PURPLE), (W-1, 0, PURPLE), (0, H-1, GREEN), (W-1, H-1, GREEN)]:
        dx = 1 if cx == 0 else -1
        dy = 1 if cy == 0 else -1
        draw.line([(cx, cy), (cx + 6*dx, cy)], fill=col, width=2)
        draw.line([(cx, cy), (cx, cy + 6*dy)], fill=col, width=2)

def draw_panel(draw, y0, y1, title="", accent=GREEN):
    """Draw a bordered panel with accent corners and optional title."""
    x0, x1 = 8, W - 9
    draw.rectangle([x0, y0, x1, y1], outline=BORDER, width=1)
    draw.line([(x0, y0), (x0 + 16, y0)], fill=accent, width=2)
    draw.line([(x0, y0), (x0, y0 + 8)], fill=accent, width=2)
    draw.line([(x1 - 16, y1), (x1, y1)], fill=accent, width=2)
    draw.line([(x1, y1 - 8), (x1, y1)], fill=accent, width=2)
    if title:
        tw = draw.textlength(title, font=FONT_TITLE)
        tx = x0 + 22
        draw.rectangle([tx - 4, y0 - 1, tx + tw + 4, y0 + 1], fill=BG)
        draw.text((tx, y0 - 7), title, fill=accent, font=FONT_TITLE)

def draw_bar(draw, x, y, w, h, pct, color=GREEN):
    """Draw a progress bar."""
    draw.rectangle([x, y, x + w, y + h], fill=GREEN_DARK)
    fill_w = int(w * min(pct, 100) / 100)
    if fill_w > 0:
        draw.rectangle([x, y, x + fill_w, y + h], fill=color)
        if fill_w > 2:
            tip = tuple(min(255, c + 60) for c in color)
            draw.line([(x + fill_w - 1, y), (x + fill_w - 1, y + h)], fill=tip)
    draw.rectangle([x, y, x + w, y + h], outline=BORDER_HI, width=1)

def draw_sparkline(draw, x, y, w, h, data, color=GREEN):
    """Draw a mini sparkline chart."""
    if not data or len(data) < 2:
        return
    draw.rectangle([x, y, x + w, y + h], fill=BG_PANEL)
    n = len(data)
    mn, mx = min(data), max(data)
    rng = mx - mn if mx != mn else 1
    step = w / (n - 1)
    points = [(x + i * step, y + h - ((v - mn) / rng) * h) for i, v in enumerate(data)]
    fill_pts = points + [(x + w, y + h), (x, y + h)]
    draw.polygon(fill_pts, fill=tuple(c // 6 for c in color))
    draw.line(points, fill=color, width=1)

def usage_color(pct):
    if pct >= 90: return RED
    if pct >= 75: return ORANGE
    return GREEN

def temp_color(t):
    if t >= 70: return RED
    if t >= 55: return ORANGE
    return GREEN

def fmt_bytes(mb):
    return f"{mb / 1000:.1f}G" if mb >= 1000 else f"{mb}M"

def fmt_views(n):
    if n >= 1_000_000: return f"{n / 1_000_000:.1f}M"
    if n >= 1000: return f"{n / 1000:.1f}K"
    return str(n)

def truncate(text, font, max_width, draw):
    """Truncate text with ellipsis to fit max_width."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    while len(text) > 1 and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…"
