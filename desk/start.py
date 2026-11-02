#!/usr/bin/env python3
# Runs the STEER app against this folder (the catalog). Settings: steer.json.
import os
import sys
from pathlib import Path

here = Path(__file__).resolve().parent

if len(sys.argv) >= 2 and sys.argv[1] == "wait-save":
    sys.path.insert(0, str(here / "app"))
    from wait_save import main as wait_main  # noqa: E402

    sys.exit(wait_main(sys.argv[2:], start_py_dir=here))

os.execv(
    sys.executable,
    [sys.executable, str(here / "app" / "server.py"), "--catalog", str(here)] + sys.argv[1:],
)
