#!/usr/bin/env python3
"""Teste simples de orientação do display."""

import time

from layout import render_orientation_frame
from shared import Screen


def main():
    screen = Screen()

    try:
        while True:
            screen.show(render_orientation_frame())

            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        screen.close()


if __name__ == "__main__":
    main()
