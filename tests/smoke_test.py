#!/usr/bin/env python3
"""Smoke test: import all modules and render frames without a physical display."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from layout import render_calibration_frame, render_orientation_frame
from system_resource import render_resources_frame
from shared import W, H


class RenderSmokeTests(unittest.TestCase):
    def test_resources_frame_size(self):
        stats = {
            "cpu": 12.5,
            "mem_pct": 40.0,
            "temp": 45.0,
            "disk_pct": 55.0,
            "net_sent": 1000,
            "net_recv": 2000,
            "uptime": 3600,
        }
        img = render_resources_frame(stats, [1.0, 2.0, 3.0])
        self.assertEqual(img.size, (W, H))

    def test_calibration_frame_size(self):
        img = render_calibration_frame()
        self.assertEqual(img.size, (W, H))

    def test_orientation_frame_size(self):
        img = render_orientation_frame()
        self.assertEqual(img.size, (W, H))

    def test_import_modules(self):
        import shared  # noqa: F401
        import system_resource  # noqa: F401
        import layout  # noqa: F401
        import screen  # noqa: F401

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
