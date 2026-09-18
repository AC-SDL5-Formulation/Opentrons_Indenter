#!/usr/bin/env python3
"""Launch the Automated Indenter dashboard.

    python run_indenter.py

Opens http://localhost:8766 (set INDENTER_UI_OPEN_BROWSER=0 to skip the browser).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

if __name__ == "__main__":
    from web_ui.server import main

    main()
