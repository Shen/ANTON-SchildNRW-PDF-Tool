#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

from modules.io_utils import appdir
from modules.settings import load_settings


def main() -> None:
    # Always launch GUI; CLI mode can be added back if desired
    from modules.gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()

