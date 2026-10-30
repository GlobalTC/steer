#!/usr/bin/env python3
# Runs the STEER app against this folder (the catalog). Settings: steer.json.
import os, sys
from pathlib import Path
here = Path(__file__).resolve().parent
os.execv(sys.executable, [sys.executable, str(here / "app" / "server.py"), "--catalog", str(here)] + sys.argv[1:])
