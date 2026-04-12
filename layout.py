#!/usr/bin/env python3
"""Shared layout frames used by screen modes."""

from datetime import datetime

from PIL import ImageDraw

from shared import (
    BORDER,
    CYAN,
    DISPLAY_MODE,
    FONT_BIG,
    FONT_DATA,
    FONT_MEGA,
    FONT_SMALL,
    FONT_TINY,
    GREEN,
    PURPLE,
    PURPLE_DIM,
    WHITE_DIM,
    W,
    H,
    draw_corners,
    new_frame,
)


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


def render_orientation_frame():
    img = new_frame()
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W // 2, H], fill=PURPLE)
    draw.rectangle([W // 2, 0, W, H], fill=GREEN)

    text = "LANDSCAPE OK"
    tw = draw.textlength(text)
    draw.text(((W - tw) // 2, H // 2 - 10), text, fill=(255, 255, 255))
    draw.line([(0, H // 2), (W, H // 2)], fill=(255, 255, 255), width=2)

    draw.text((14, H - 18), f"MODE: {DISPLAY_MODE}", fill=WHITE_DIM, font=FONT_TINY)
    draw.text((W - 86, H - 18), datetime.now().strftime("%H:%M:%S"), fill=WHITE_DIM, font=FONT_TINY)
    draw_corners(draw)
    return img
